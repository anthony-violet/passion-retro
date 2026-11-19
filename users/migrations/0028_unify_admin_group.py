"""Fusionne les anciennes orthographes du groupe admin dans « Administrateur »."""

from django.db import migrations

ADMIN_GROUP = 'Administrateur'
LEGACY_NAMES = ('Administrateurs', 'Admininistrateur')


def unify_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('users', 'User')
    admin, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
    for legacy in Group.objects.filter(name__in=LEGACY_NAMES):
        for user in User.objects.filter(groups=legacy):
            user.groups.add(admin)
        admin.permissions.add(*legacy.permissions.all())
        legacy.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0027_utm'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(unify_admin_group, migrations.RunPython.noop),
    ]
