"""Retire les faux visiteurs belges laissés par un robot avant le signal JavaScript."""

from django.db import migrations


def purge(apps, schema_editor):
    from users.visits import purge_bot_bursts

    purge_bot_bursts(apps.get_model('users', 'Visit'), apps.get_model('users', 'VisitorStats'))


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0031_featured_collectible_showcase'),
    ]

    operations = [
        migrations.RunPython(purge, migrations.RunPython.noop),
    ]
