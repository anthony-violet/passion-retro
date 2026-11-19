"""Protection anti-spam du livre d'or, sans service extérieur.

- champ piège invisible que seuls les robots remplissent ;
- délai minimal entre l'affichage du formulaire et l'envoi ;
- limite de messages par visiteur et par heure ;
- refus des liens et des doublons.

L'adresse IP n'est jamais stockée en clair : seule une empreinte HMAC
(non réversible sans la clé secrète du site) sert à compter les envois.
"""

import hashlib
import hmac
import re
import time
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from users.visits import client_ip

HONEYPOT_FIELD = 'website'
TIMESTAMP_FIELD = 'form_token'
MIN_FILL_SECONDS = 3
MAX_FORM_AGE_SECONDS = 24 * 3600
MAX_MESSAGES_PER_HOUR = 3
DUPLICATE_WINDOW = timedelta(days=1)

LINK_PATTERN = re.compile(r'(https?://|www\.|\[url|\[img|<a\s)', re.IGNORECASE)
_SIGNING_SALT = 'guestbook.form-token'


def ip_fingerprint(request):
    ip = client_ip(request)
    if not ip:
        return ''
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()


def make_form_token():
    return signing.dumps(int(time.time()), salt=_SIGNING_SALT)


def form_token_is_valid(token):
    """Vrai si le formulaire a été affiché il y a plus de MIN_FILL_SECONDS."""
    try:
        issued = signing.loads(token or '', salt=_SIGNING_SALT, max_age=MAX_FORM_AGE_SECONDS)
    except signing.BadSignature:
        return False
    return time.time() - int(issued) >= MIN_FILL_SECONDS


def contains_link(text):
    return bool(LINK_PATTERN.search(text or ''))


def too_many_messages(fingerprint):
    from .models import Guestbook

    if not fingerprint:
        return False
    since = timezone.now() - timedelta(hours=1)
    return Guestbook.objects.filter(ip_hash=fingerprint, created__gte=since).count() >= MAX_MESSAGES_PER_HOUR


def is_duplicate(content):
    from .models import Guestbook

    since = timezone.now() - DUPLICATE_WINDOW
    return Guestbook.objects.filter(content__iexact=content.strip(), created__gte=since).exists()
