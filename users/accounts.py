"""Validation des comptes par e-mail.

À l'inscription, le compte est créé désactivé (``User.active = False``) et un
lien d'activation est envoyé. Le jeton est propre à l'activation : il ne peut
pas servir à réinitialiser un mot de passe, et il devient invalide dès que le
compte est activé.
"""

import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

logger = logging.getLogger(__name__)


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'users.accounts.AccountActivationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        # Inclure l'état « active » rend le lien inutilisable après activation.
        return f'{user.pk}{user.password}{timestamp}{user.active}'


activation_token = AccountActivationTokenGenerator()


def activation_url(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse('activate', args=[uid, activation_token.make_token(user)])
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def send_activation_email(user):
    """Envoie le lien d'activation. Renvoie False si l'envoi a échoué."""
    context = {
        'user': user,
        'activation_link': activation_url(user),
        'site_name': settings.SITE_NAME,
    }
    try:
        send_mail(
            f'Active ton compte {settings.SITE_NAME}',
            render_to_string('emails/activation_account.txt', context),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=render_to_string('emails/activation_account.html', context),
        )
    except Exception:  # SMTP indisponible : le membre pourra redemander le lien
        logger.exception("Échec de l'envoi de l'e-mail d'activation à l'utilisateur %s", user.pk)
        return False
    return True


def user_from_uid(uidb64):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
