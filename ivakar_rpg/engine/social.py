"""Présence des héros et taverne (fil de discussion par lieu)."""
from datetime import timedelta

from django.utils import timezone

from ..models import Character, LocationMessage
from . import RpgError

# Un héros actif depuis moins de PRESENCE_MINUTES est « présent » dans son lieu.
PRESENCE_MINUTES = 10
# Pour ne pas écrire en base à chaque page : la présence est rafraîchie au plus une fois par minute.
SEEN_REFRESH_SECONDS = 60
MESSAGE_MAX_LENGTH = 300
MESSAGE_COOLDOWN_SECONDS = 5
TAVERN_SIZE = 30


def touch(character, now=None):
    """Note que le héros est actif (sans verrou : simple horodatage)."""
    now = now or timezone.now()
    if character.last_seen_at and (now - character.last_seen_at).total_seconds() < SEEN_REFRESH_SECONDS:
        return
    Character.objects.filter(pk=character.pk).update(last_seen_at=now)
    character.last_seen_at = now


def present_heroes(character, now=None):
    """Autres héros actifs récemment dans le même lieu."""
    if not character.location_id:
        return Character.objects.none()
    since = (now or timezone.now()) - timedelta(minutes=PRESENCE_MINUTES)
    return (Character.objects.filter(location_id=character.location_id, last_seen_at__gte=since)
            .exclude(pk=character.pk).select_related('user').order_by('name'))


def tavern(location, after_id=None):
    """Derniers messages visibles d'un lieu, du plus ancien au plus récent."""
    messages = LocationMessage.objects.filter(location=location, is_hidden=False).select_related('character')
    if after_id:
        messages = messages.filter(pk__gt=after_id)
    return list(reversed(messages[:TAVERN_SIZE]))


def say(character, text, now=None):
    """Poste un message dans la taverne du lieu où se trouve le héros."""
    now = now or timezone.now()
    text = ' '.join((text or '').split())
    if not text:
        raise RpgError("Ton message est vide.")
    if len(text) > MESSAGE_MAX_LENGTH:
        raise RpgError(f"Ton message dépasse {MESSAGE_MAX_LENGTH} caractères.")
    if not character.location_id:
        raise RpgError("Tu n'es nulle part.")
    if character.is_ko:
        raise RpgError("Tu es inconscient.")
    recent = LocationMessage.objects.filter(
        character=character, created_at__gte=now - timedelta(seconds=MESSAGE_COOLDOWN_SECONDS)).exists()
    if recent:
        raise RpgError("Doucement : attends quelques secondes avant de reparler.")
    touch(character, now)
    return LocationMessage.objects.create(location_id=character.location_id, character=character, text=text)
