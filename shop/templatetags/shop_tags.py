from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def featured_collectible(person):
    """Petite icône de l'objet de collection mis en avant par ``person`` (vide sinon)."""
    item = getattr(person, 'featured_collectible', None) if getattr(person, 'featured_collectible_id', None) else None
    if item is None:
        return ''
    label = f"Objet fétiche : {item.name} ({item.get_rarity_display()})"
    visual = (format_html('<img src="{}" alt="">', item.visual_url) if item.visual_url
              else format_html('<span aria-hidden="true">💎</span>'))
    return format_html(
        '<span class="featured-collectible featured-collectible--{}" title="{}" role="img" aria-label="{}">{}</span>',
        item.rarity, label, label, visual,
    )
