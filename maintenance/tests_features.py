"""Mode maintenance : redirection des visiteurs, accès des superutilisateurs."""

from django.test import TestCase, override_settings
from django.conf import settings
from django.urls import reverse

from maintenance.models import Informations
from users.models import User

WITH_MAINTENANCE = settings.MIDDLEWARE + ['maintenance.middleware.MaintenanceMiddleware']


@override_settings(MIDDLEWARE=WITH_MAINTENANCE)
class MaintenanceModeTest(TestCase):
    def test_site_open_without_maintenance_record(self):
        self.assertEqual(self.client.get(reverse('guestbook_home')).status_code, 200)

    def test_info_page_404_without_record(self):
        self.assertEqual(self.client.get(reverse('maintenance:info')).status_code, 404)

    def test_visitors_redirected_when_active(self):
        Informations.objects.create(pk=1, is_active=True)
        response = self.client.get(reverse('guestbook_home'))
        self.assertRedirects(response, reverse('maintenance:info'))

    def test_info_page_shows_message(self):
        Informations.objects.create(pk=1, is_active=True, name='Mise à jour', content='Retour vite')
        response = self.client.get(reverse('maintenance:info'))
        self.assertContains(response, 'Retour vite')

    def test_members_also_redirected(self):
        Informations.objects.create(pk=1, is_active=True)
        self.client.force_login(User.objects.create_user(username='m', password='p'))
        self.assertEqual(self.client.get(reverse('forum_home')).status_code, 302)

    def test_superuser_bypasses_maintenance(self):
        Informations.objects.create(pk=1, is_active=True)
        self.client.force_login(User.objects.create_superuser(username='root', email='r@t.com', password='p'))
        self.assertEqual(self.client.get(reverse('guestbook_home')).status_code, 200)

    def test_inactive_maintenance_lets_everyone_in(self):
        Informations.objects.create(pk=1, is_active=False)
        self.assertEqual(self.client.get(reverse('guestbook_home')).status_code, 200)
