from django import template

register = template.Library()


@register.filter(name='has_group')
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


@register.inclusion_tag('components/user_level_badge.html')
def user_level_badge(user, variant='avatar', compact=False):
    if user is None or not getattr(user, 'is_authenticated', False):
        return {}

    level = user.level_number
    title = user.level_title

    classes = ['level-badge']
    if variant == 'inline':
        classes.append('level-badge--inline')
    if compact:
        classes.append('level-badge--compact')

    return {
        'level': level,
        'title': title,
        'classes': ' '.join(classes),
    }

@register.filter(name='first_item')
def first_item(value, max_length=25):
    """Premier élément d'une liste saisie librement (« SNES, MegaDrive ; NES »).

    Coupe sur la première virgule ou le premier point-virgule, retire les espaces
    et tronque à `max_length` caractères (avec « … ») pour les affichages condensés.
    """
    if not value:
        return ''
    first = str(value).replace(';', ',').split(',')[0].strip()
    max_length = int(max_length)
    if len(first) > max_length:
        first = first[:max_length - 1].rstrip() + '…'
    return first
