"""Nom unique du groupe admin et migration des anciennes orthographes."""

from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from users.groups import ADMIN_GROUP, ADMIN_GROUPS, FORUM_MODERATOR_GROUPS, LEGACY_ADMIN_NAMES
from users.models import User

migration = import_module('users.migrations.0028_unify_admin_group')


class AdminGroupTest(TestCase):
    def test_single_admin_name(self):
        self.assertEqual(ADMIN_GROUP, 'Administrateur')
        self.assertIn(ADMIN_GROUP, ADMIN_GROUPS)
        self.assertIn(ADMIN_GROUP, FORUM_MODERATOR_GROUPS)
        for legacy in LEGACY_ADMIN_NAMES:
            self.assertNotIn(legacy, ADMIN_GROUPS + FORUM_MODERATOR_GROUPS)

    def test_migration_merges_legacy_groups(self):
        alice = User.objects.create_user(username='alice', password='p')
        bob = User.objects.create_user(username='bob', password='p')
        alice.groups.add(Group.objects.create(name='Administrateurs'))
        bob.groups.add(Group.objects.create(name='Admininistrateur'))

        migration.unify_admin_group(apps, None)

        admin = Group.objects.get(name=ADMIN_GROUP)
        self.assertEqual(set(User.objects.filter(groups=admin)), {alice, bob})
        self.assertFalse(Group.objects.filter(name__in=LEGACY_ADMIN_NAMES).exists())

    def test_migration_is_idempotent(self):
        migration.unify_admin_group(apps, None)
        migration.unify_admin_group(apps, None)
        self.assertEqual(Group.objects.filter(name=ADMIN_GROUP).count(), 1)

    def test_administrateur_can_see_pending_posts(self):
        admin = User.objects.create_user(username='admin', password='p')
        admin.groups.add(Group.objects.get_or_create(name=ADMIN_GROUP)[0])
        self.client.force_login(admin)
        url = reverse('create_news', args=['news'])
        self.assertNotEqual(self.client.get(url).status_code, 403)
