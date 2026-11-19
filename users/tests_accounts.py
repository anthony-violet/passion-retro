"""Inscription avec validation par e-mail et mot de passe oublié."""

import re
from unittest import mock

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users import accounts
from users.models import User

STRONG_PASSWORD = 'Megadrive-16bits!'


PROD_VALIDATORS = [
    {'NAME': f'django.contrib.auth.password_validation.{name}'}
    for name in ('UserAttributeSimilarityValidator', 'MinimumLengthValidator',
                 'CommonPasswordValidator', 'NumericPasswordValidator')
]


def link_in(message):
    return re.search(r'http://testserver(/\S+)', message.body).group(1)


@override_settings(GOOGLE_PRIVATE_KEY='cle-test', AUTH_PASSWORD_VALIDATORS=PROD_VALIDATORS)
class RegistrationActivationTest(TestCase):
    def register(self, **overrides):
        data = {
            'username': 'sonic', 'email': 'sonic@test.com',
            'password1': STRONG_PASSWORD, 'password2': STRONG_PASSWORD,
            'g-recaptcha-response': 'ok',
        }
        data.update(overrides)
        with mock.patch('users.views._recaptcha_ok', return_value=True):
            return self.client.post(reverse('register'), data)

    def test_registration_creates_inactive_account_and_sends_email(self):
        response = self.register()
        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='sonic')
        self.assertFalse(user.active)
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['sonic@test.com'])
        self.assertIn('/users/activate/', mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].alternatives)  # version HTML

    def test_inactive_account_cannot_log_in(self):
        self.register()
        response = self.client.post(reverse('login'), {'username': 'sonic', 'password': STRONG_PASSWORD}, follow=True)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, "pas encore activé")

    def test_activation_link_activates_then_login_works(self):
        self.register()
        response = self.client.get(link_in(mail.outbox[0]))
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.get(username='sonic').active)
        self.client.post(reverse('login'), {'username': 'sonic', 'password': STRONG_PASSWORD})
        self.assertIn('_auth_user_id', self.client.session)

    def test_activation_link_works_once(self):
        self.register()
        link = link_in(mail.outbox[0])
        self.client.get(link)
        response = self.client.get(link, follow=True)
        self.assertContains(response, "déjà activé")

    def test_invalid_activation_link(self):
        self.register()
        user = User.objects.get(username='sonic')
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        for path in (reverse('activate', args=[uid, 'faux-jeton']), reverse('activate', args=['xx', 'faux'])):
            with self.subTest(path=path):
                self.assertRedirects(self.client.get(path), reverse('resend_activation'))
        self.assertFalse(User.objects.get(username='sonic').active)

    def test_password_reset_token_cannot_activate(self):
        self.register()
        user = User.objects.get(username='sonic')
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        self.client.get(reverse('activate', args=[uid, default_token_generator.make_token(user)]))
        self.assertFalse(User.objects.get(username='sonic').active)

    def test_failed_captcha_creates_nothing(self):
        with mock.patch('users.views._recaptcha_ok', return_value=False):
            self.client.post(reverse('register'), {
                'username': 'sonic', 'email': 's@test.com',
                'password1': STRONG_PASSWORD, 'password2': STRONG_PASSWORD,
            })
        self.assertFalse(User.objects.filter(username='sonic').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_username_or_email_rejected(self):
        User.objects.create_user(username='Sonic', email='SONIC@test.com', password='x')
        for overrides in ({'email': 'autre@test.com'}, {'username': 'tails'}):
            with self.subTest(overrides=overrides):
                response = self.register(**overrides)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch_and_weak_password(self):
        self.assertEqual(self.register(password2='autre-chose-123').status_code, 200)
        self.assertEqual(self.register(password1='123', password2='123').status_code, 200)
        self.assertFalse(User.objects.filter(username='sonic').exists())

    def test_form_errors_are_kept_on_redisplay(self):
        response = self.register(password2='autre-chose-123')
        self.assertContains(response, "ne correspondent pas")
        self.assertContains(response, 'value="sonic"')

    def test_email_failure_still_creates_account(self):
        with mock.patch('users.accounts.send_mail', side_effect=OSError('SMTP')), \
                self.assertLogs('users.accounts', level='ERROR'):
            response = self.register()
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(username='sonic', active=False).exists())

    def test_resend_activation(self):
        self.register()
        mail.outbox.clear()
        response = self.client.post(reverse('resend_activation'), {'email': 'SONIC@test.com'})
        self.assertRedirects(response, reverse('login'))
        self.assertEqual(len(mail.outbox), 1)
        self.client.get(link_in(mail.outbox[0]))
        self.assertTrue(User.objects.get(username='sonic').active)

    def test_resend_does_not_reveal_unknown_or_active_accounts(self):
        User.objects.create_user(username='actif', email='actif@test.com', password='x', active=True)
        for email in ('inconnu@test.com', 'actif@test.com'):
            with self.subTest(email=email):
                response = self.client.post(reverse('resend_activation'), {'email': email}, follow=True)
                self.assertContains(response, "Si un compte non activé correspond")
        self.assertEqual(len(mail.outbox), 0)

    def test_existing_active_members_still_log_in(self):
        User.objects.create_user(username='ancien', password=STRONG_PASSWORD, active=True)
        self.client.post(reverse('login'), {'username': 'ancien', 'password': STRONG_PASSWORD})
        self.assertIn('_auth_user_id', self.client.session)


@override_settings(AUTH_PASSWORD_VALIDATORS=PROD_VALIDATORS)
class PasswordResetTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='mario', email='mario@test.com', password='ancien-mot-de-passe', active=True
        )

    def request_reset(self, email='mario@test.com'):
        return self.client.post(reverse('password_reset'), {'email': email})

    def test_login_page_links_to_reset_and_resend(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, reverse('password_reset'))
        self.assertContains(response, reverse('resend_activation'))

    def test_reset_request_sends_email(self):
        response = self.request_reset('MARIO@test.com')
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['mario@test.com'])
        self.assertIn('Réinitialisation', message.subject)
        self.assertIn('mario', message.body)
        self.assertIn('/users/mot-de-passe-oublie/', link_in(message))

    def test_unknown_email_gives_same_answer_without_email(self):
        response = self.request_reset('personne@test.com')
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow(self):
        self.request_reset()
        response = self.client.get(link_in(mail.outbox[0]), follow=True)
        self.assertContains(response, 'new_password1')
        response = self.client.post(response.redirect_chain[-1][0], {
            'new_password1': STRONG_PASSWORD, 'new_password2': STRONG_PASSWORD,
        })
        self.assertRedirects(response, reverse('login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PASSWORD))
        self.client.post(reverse('login'), {'username': 'mario', 'password': STRONG_PASSWORD})
        self.assertIn('_auth_user_id', self.client.session)

    def test_reset_link_works_only_once(self):
        self.request_reset()
        link = link_in(mail.outbox[0])
        response = self.client.get(link, follow=True)
        set_url = response.redirect_chain[-1][0]
        self.client.post(set_url, {'new_password1': STRONG_PASSWORD, 'new_password2': STRONG_PASSWORD})
        response = self.client.get(link, follow=True)
        self.assertContains(response, 'invalide ou a déjà servi')

    def test_weak_password_rejected(self):
        self.request_reset()
        response = self.client.get(link_in(mail.outbox[0]), follow=True)
        self.client.post(response.redirect_chain[-1][0], {'new_password1': '123', 'new_password2': '123'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ancien-mot-de-passe'))

    def test_invalid_reset_link(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse('password_reset_confirm', args=[uid, 'faux-jeton']))
        self.assertContains(response, 'invalide ou a déjà servi')

    def test_reset_activates_unvalidated_account(self):
        self.user.active = False
        self.user.save()
        self.request_reset()
        response = self.client.get(link_in(mail.outbox[0]), follow=True)
        self.client.post(response.redirect_chain[-1][0], {
            'new_password1': STRONG_PASSWORD, 'new_password2': STRONG_PASSWORD,
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.active)

    def test_activation_token_cannot_reset_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = accounts.activation_token.make_token(self.user)
        response = self.client.get(reverse('password_reset_confirm', args=[uid, token]), follow=True)
        self.assertContains(response, 'invalide ou a déjà servi')
