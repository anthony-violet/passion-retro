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