"""Thèmes que les membres peuvent choisir, et ceux qu'il faut acheter en boutique."""

# Code du thème -> nom affiché dans le menu.
MEMBER_THEMES = [
    ('default', 'Default'),
    ('rpg', 'RPG'),
    ('retrorpg', 'RetroRPG'),
    ('80s', '80s'),
    ('00s', '00s'),
    ('vhs', 'VHS'),
    ('modern', 'Modern'),
]
THEME_LABELS = dict(MEMBER_THEMES)

# Ces thèmes se débloquent en achetant l'objet « thème » correspondant
# (Item.kind == 'theme' et Item.css_class == code du thème).
PAID_THEMES = {'rpg', 'modern', '80s'}


def owned_themes(user):
    """Codes des thèmes payants que ``user`` possède dans son inventaire."""
    if not getattr(user, 'is_authenticated', False):
        return set()
    from shop.models import Item

    return set(
        user.inventory.filter(item__kind=Item.KIND_THEME, quantity__gt=0)
        .values_list('item__css_class', flat=True)
    )


def can_use_theme(user, code, owned=None):
    if code not in THEME_LABELS:
        return False
    if code not in PAID_THEMES:
        return True
    return code in (owned if owned is not None else owned_themes(user))


def theme_options(user):
    """[(code, nom, verrouillé)] pour le sélecteur de thème du membre."""
    owned = owned_themes(user)
    return [(code, label, not can_use_theme(user, code, owned)) for code, label in MEMBER_THEMES]
