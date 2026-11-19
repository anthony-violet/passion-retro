"""Déduit le type et la classe CSS des objets existants depuis leur catégorie."""
from datetime import datetime, timezone

from django.db import migrations
from django.utils.text import slugify

THEME_CODES = {'00s', '80s', 'rpg', 'retrorpg', 'vhs', 'modern', 'vicecity', 'doomsday'}


def guess_kind(category_name):
    name = slugify(category_name)
    if 'cadre' in name:
        return 'frame'
    if 'pseudo' in name:
        return 'username'
    if 'theme' in name:
        return 'theme'
    return 'collectible'


def theme_code(item_name):
    slug = slugify(item_name)
    for code in sorted(THEME_CODES, key=len, reverse=True):
        if slug.endswith(code):
            return code
    return slug.replace('theme-', '', 1)


def forwards(apps, schema_editor):
    Item = apps.get_model('shop', 'Item')
    for item in Item.objects.select_related('category'):
        kind = guess_kind(item.category.name)
        item.kind = kind
        if not item.css_class:
            item.css_class = theme_code(item.name) if kind == 'theme' else slugify(item.name)
        # Les objets déjà en vente ne doivent pas tous apparaître comme « Nouveau ».
        item.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        item.save(update_fields=['kind', 'css_class', 'created_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_item_shop_mechanics'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
