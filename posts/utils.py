from django.utils.text import slugify

from .models import Post


def unique_slug(title, exclude_pk=None):
    """Retourne un slug unique pour un Post, basé sur le titre."""
    base = (slugify(title) or 'article')[:190]
    slug = base
    index = 2
    qs = Post.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug = f'{base}-{index}'
        index += 1
    return slug


def contribution_categories():
    """Catégories proposées aux contributeurs : celles affichées dans le menu."""
    from .models import Category, NavSection

    sections = (
        NavSection.objects.filter(visible=True, category__isnull=False)
        .select_related('category')
        .order_by('order', 'label')
    )
    seen = set()
    choices = []
    for section in sections:
        if section.category_id in seen:
            continue
        seen.add(section.category_id)
        label = f'{section.icon} {section.label}'.strip()
        choices.append((section.category, label))
    if not choices:
        choices = [(cat, cat.name) for cat in Category.objects.order_by('name')]
    return choices
