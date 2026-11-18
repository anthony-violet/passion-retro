"""Rend l'or perdu aux joueurs qui n'avaient pas encore d'or dans leur inventaire.

Avant le correctif de ``users.leveling._add_gold``, l'or des passages de niveau
était perdu en silence pour ces joueurs. On leur crée l'entrée « Or » avec l'or
de départ et l'or de chaque niveau atteint depuis le niveau 2. Les valeurs sont
recopiées ici pour que la migration ne change pas si le barème évolue.
"""
from django.db import migrations

STARTING_GOLD = 100


def gold_for_level(level):
    return 10 + 2 * level


def restore_gold(apps, schema_editor):
    Item = apps.get_model('shop', 'Item')
    UserLevel = apps.get_model('users', 'UserLevel')
    UserInventory = apps.get_model('users', 'UserInventory')

    gold_item = Item.objects.filter(name='Or').first()
    if gold_item is None:
        return

    has_gold = UserInventory.objects.filter(item=gold_item).values('user_id')
    for user_level in UserLevel.objects.filter(level__gte=2).exclude(user_id__in=has_gold):
        owed = STARTING_GOLD + sum(gold_for_level(lvl) for lvl in range(2, user_level.level + 1))
        UserInventory.objects.create(user_id=user_level.user_id, item=gold_item, quantity=owed)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0024_user_announcements'),
        ('shop', '0002_item_category_alter_item_image'),
    ]

    operations = [
        migrations.RunPython(restore_gold, migrations.RunPython.noop),
    ]
