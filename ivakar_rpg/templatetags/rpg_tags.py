from django import template

register = template.Library()


@register.simple_tag
def rpg_title(user):
    """Titre Ivakar du membre (palier de niveau RPG), ``''`` s'il n'en a pas ou l'a masqué."""
    from ..decorators import rpg_is_visible
    from ..engine.rewards import current_title
    from ..models import Character

    if user is None or not getattr(user, 'pk', None) or not rpg_is_visible(user):
        return ''
    character = Character.objects.filter(user_id=user.pk).first()
    return current_title(character)


@register.filter
def hp_percent(value, maximum):
    try:
        return max(0, min(100, int(value) * 100 // max(1, int(maximum))))
    except (TypeError, ValueError):
        return 0
