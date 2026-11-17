from django import template
from django.utils import timezone

from home.templatetags.vice_tags import wanted_stars
from passion_retro.seasonal import DOOMSDAY_RELEASE

register = template.Library()

THREAT_LABELS = ["Inconnue", "Faible", "Modérée", "Élevée", "Critique", "Apocalyptique"]


@register.simple_tag
def threat_level(user):
    """Jauge « niveau de menace » du HUD : même barème que les étoiles Vice City
    (un cran par tranche de 10 niveaux, 1 à 5 ; 0 pour un visiteur)."""
    segments = wanted_stars(user)
    level = sum(segments)
    return {"segments": segments, "level": level, "label": THREAT_LABELS[level]}


@register.simple_tag
def doomsday_countdown():
    """Jours restants avant la sortie en salles (0 le jour J, négatif ensuite)."""
    days = (DOOMSDAY_RELEASE - timezone.localdate()).days
    return {"days": days, "release": DOOMSDAY_RELEASE}
