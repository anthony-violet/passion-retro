"""Seuls RPG, Modern et 80s restent payants ; les autres thèmes sont gratuits."""
from django.db import migrations

PAID = {
    # code: (nom par défaut, prix par défaut, rareté)
    'rpg': ('Thème RPG', 150, 'rare'),
    'modern': ('Thème Modern', 200, 'rare'),
    '80s': ('Thème Rétro 80s', 250, 'epic'),
}


def forwards(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    Item = apps.get_model('shop', 'Item')
    User = apps.get_model('users', 'User')
    UserInventory = apps.get_model('users', 'UserInventory')

    existing = Item.objects.filter(kind='theme')
    category = existing.first().category if existing.exists() else None
    if category is None:
        category, _ = Category.objects.get_or_create(name='Thèmes', defaults={'description': 'Thèmes du site'})

    for code, (name, price, rarity) in PAID.items():
        item = existing.filter(css_class=code).order_by('pk').first()
        if item is None:
            item = Item.objects.create(category=category, name=name, kind='theme', css_class=code,
                                       price=price, rarity=rarity,
                                       description=f"Débloque le thème {name.replace('Thème ', '')} pour tout le site.")
        else:
            item.is_active = True
            item.rarity = rarity
            item.save(update_fields=['is_active', 'rarity'])
        # Les membres qui utilisent déjà ce thème le gardent.
        for user_id in User.objects.filter(theme=code).values_list('pk', flat=True):
            UserInventory.objects.get_or_create(user_id=user_id, item=item, defaults={'quantity': 1})

    # Les thèmes devenus gratuits ne sont plus vendus (les exemplaires achetés restent).
    existing.exclude(css_class__in=PAID).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0004_item_kinds'),
        ('users', '0030_user_wallet'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
