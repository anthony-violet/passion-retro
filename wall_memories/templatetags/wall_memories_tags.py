import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from commons.bbcode_parser import BBCodeParser

register = template.Library()

# Après échappement, seuls les liens et images http(s) ou relatifs sont conservés.
_UNSAFE_URL = re.compile(
    r'''(href|src)="\s*(?!https?://|/|#)[^"]*"''',
    flags=re.IGNORECASE,
)


@register.filter(name='safe_bbcode')
def safe_bbcode(value):
    """BBCode sûr : le HTML saisi par le membre est échappé avant conversion.

    Les commentaires du Mur sont publiés sans validation préalable, on ne peut
    donc pas laisser passer de HTML ni d'URL ``javascript:``.
    """
    if not value:
        return ''
    html = BBCodeParser().parse(escape(value))
    html = _UNSAFE_URL.sub(r'\1="#"', html)
    html = html.replace('\r\n', '\n').replace('\n', '<br>')
    return mark_safe(html)


@register.filter(name='plain_excerpt')
def plain_excerpt(value, length=260):
    """Extrait sans balises BBCode, pour les cartes du mur."""
    if not value:
        return ''
    text = re.sub(r'\[/?[^\]]{1,40}\]', '', value)
    text = re.sub(r'\s+', ' ', text).strip()
    length = int(length)
    if len(text) <= length:
        return text
    return text[:length].rsplit(' ', 1)[0] + '…'
