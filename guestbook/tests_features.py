"""Livre d'or : dépôt de messages, validation, modération et anti-spam."""

from datetime import timedelta
from unittest import mock

from django.core import signing
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from guestbook import antispam
from guestbook.models import Guestbook
from users.models import User

IP = '203.0.113.42'


class GuestbookTestBase(TestCase):
    url = reverse('guestbook_home')

    def setUp(self):
        # Le délai minimal de remplissage est testé à part.
        patcher = mock.patch.object(antispam, 'MIN_FILL_SECONDS', 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def send(self, author='Toto', content='Super site !', ip=IP, **extra):
        data = {'author': author, 'content': content, 'form_token': antispam.make_form_token()}
        data.update(extra)
        return self.client.post(self.url, data, REMOTE_ADDR=ip)


class GuestbookFeatureTest(GuestbookTestBase):
    def test_post_message_then_redirect(self):
        response = self.send()
        self.assertRedirects(response, self.url)
        self.assertTrue(Guestbook.objects.filter(author='Toto', content='Super site !').exists())
        self.assertContains(self.client.get(self.url), 'Super site !')

    def test_empty_message_rejected(self):
        response = self.send(content='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_message_longer_than_model_limit_rejected(self):
        response = self.send(content='x' * 101)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_author_longer_than_model_limit_rejected(self):
        self.send(author='x' * 51, content='Salut')
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_html_is_escaped(self):
        Guestbook.objects.create(author='Pirate', content='<script>alert(1)</script>')
        response = self.client.get(self.url)
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_deactivated_entries_hidden(self):
        Guestbook.objects.create(author='A', content='Visible')
        Guestbook.objects.create(author='B', content='Masqué par la modération', active=False)
        response = self.client.get(self.url)
        self.assertContains(response, 'Visible')
        self.assertNotContains(response, 'Masqué par la modération')

    def test_pagination_by_ten(self):
        Guestbook.objects.bulk_create([Guestbook(author='A', content=f'M{i}') for i in range(15)])
        response = self.client.get(self.url, {'page': 2})
        self.assertEqual(len(response.context['guestbook']), 5)


class GuestbookAntiSpamTest(GuestbookTestBase):
    def test_honeypot_filled_saves_nothing(self):
        response = self.send(website='http://spam.example')
        self.assertRedirects(response, self.url)
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_missing_token_saves_nothing(self):
        self.client.post(self.url, {'author': 'Bot', 'content': 'Salut'}, REMOTE_ADDR=IP)
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_forged_token_saves_nothing(self):
        self.send(form_token=signing.dumps(0, salt='autre-sel'))
        self.send(form_token='nimportequoi')
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_too_fast_submission_saves_nothing(self):
        with mock.patch.object(antispam, 'MIN_FILL_SECONDS', 3):
            self.send()
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_submission_after_delay_is_saved(self):
        with mock.patch.object(antispam, 'MIN_FILL_SECONDS', 3):
            token = antispam.make_form_token()
            now = antispam.time.time()
            with mock.patch.object(antispam.time, 'time', return_value=now + 5):
                self.client.post(self.url, {
                    'author': 'Humain', 'content': 'Patient', 'form_token': token,
                }, REMOTE_ADDR=IP)
        self.assertTrue(Guestbook.objects.filter(author='Humain').exists())

    def test_fourth_message_within_hour_refused(self):
        for i in range(3):
            self.send(content=f'Message {i}')
        response = self.send(content='Message 4')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Réessayez dans une heure')
        self.assertEqual(Guestbook.objects.count(), 3)

    def test_limit_is_per_visitor(self):
        for i in range(3):
            self.send(content=f'Message {i}')
        self.send(content='Autre visiteur', ip='198.51.100.7')
        self.assertTrue(Guestbook.objects.filter(content='Autre visiteur').exists())

    def test_limit_resets_after_an_hour(self):
        for i in range(3):
            self.send(content=f'Message {i}')
        Guestbook.objects.update(created=timezone.now() - timedelta(hours=2))
        self.send(content='Plus tard')
        self.assertTrue(Guestbook.objects.filter(content='Plus tard').exists())

    def test_staff_not_limited(self):
        self.client.force_login(User.objects.create_user(username='staff', password='p', is_staff=True))
        for i in range(5):
            self.send(content=f'Annonce {i}')
        self.assertEqual(Guestbook.objects.count(), 5)

    def test_links_refused(self):
        for content in ('Va sur http://spam.fr', 'www.casino.com', '[url=x]clic[/url]', 'HTTPS://A.B'):
            with self.subTest(content=content):
                response = self.send(content=content)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Les liens ne sont pas autorisés')
        self.assertEqual(Guestbook.objects.count(), 0)

    def test_duplicate_refused(self):
        self.send(content='Coucou tout le monde')
        response = self.send(content='  coucou TOUT le monde ', ip='198.51.100.7')
        self.assertContains(response, 'déjà été publié')
        self.assertEqual(Guestbook.objects.count(), 1)

    def test_ip_fingerprint_stored_not_ip(self):
        self.send()
        entry = Guestbook.objects.get()
        self.assertEqual(len(entry.ip_hash), 64)
        self.assertNotIn(IP, entry.ip_hash)
        self.assertNotEqual(entry.ip_hash, IP)

    def test_honeypot_present_but_hidden(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="website"')
        self.assertContains(response, 'class="guestbook-trap" aria-hidden="true"')
        self.assertContains(response, 'tabindex="-1"')
        self.assertContains(response, 'name="form_token"')
