from django import template

register = template.Library()

WANTED_MAX = 5


@register.simple_tag
def wanted_stars(user):
    """Étoiles de recherche façon HUD : une étoile par tranche de 10 niveaux (1 à 5).

    Purement décoratif, lu depuis le niveau du membre ; 0 pour un visiteur.
    """
    if not getattr(user, "is_authenticated", False):
        level = 0
    else:
        level = min(WANTED_MAX, max(1, -(-user.level_number // 10)))
    return [i < level for i in range(WANTED_MAX)]
