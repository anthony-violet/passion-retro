from allauth.account.signals import email_confirmed
from django.dispatch import receiver


@receiver(email_confirmed)
def activate_user_on_email_confirmed(sender, request, email_address, **kwargs):
    """Active le compte quand allauth confirme l'adresse email."""
    user = email_address.user
    if not user.active:
        user.active = True
        user.save(update_fields=["active"])
