from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.dateformat import format as date_format

register = template.Library()

NEW_DELAY = timedelta(hours=48)


@register.filter
def ago(value):
    """Date relative courte : « il y a 3 h », « hier », « il y a 2 sem. »."""
    if not value:
        return ''
    now = timezone.now()
    delta = now - value
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        return f"il y a {seconds // 60} min"
    if seconds < 86400:
        return f"il y a {seconds // 3600} h"
    days = delta.days
    if days == 1:
        return 'hier'
    if days < 7:
        return f'il y a {days} j'
    if days < 31:
        return f'il y a {days // 7} sem.'
    return f"le {date_format(timezone.localtime(value), 'j F Y')}"


@register.filter
def is_new(value):
    return bool(value) and timezone.now() - value < NEW_DELAY


@register.filter
def cover_hue(post):
    """Teinte stable pour l'image de repli d'une actu sans illustration."""
    return (getattr(post, 'pk', 0) or 0) * 47 % 360


@register.filter
def cover_glyph(post):
    category = getattr(getattr(post, 'category', None), 'name', '') or 'PR'
    letters = ''.join(ch for ch in category if ch.isalnum())
    return letters[:3].upper() or 'PR'


@register.filter
def initials(user):
    name = getattr(user, 'username', '') or '?'
    letters = ''.join(ch for ch in name if ch.isalnum())
    return (letters[:2] or '?').upper()


@register.filter
def plain(value, limit=140):
    """Texte brut (sans BBCode ni HTML) tronqué, pour les extraits."""
    from django.utils.html import strip_tags
    from passion_retro.seo import plain_text

    return plain_text(strip_tags(value or ''), int(limit))
