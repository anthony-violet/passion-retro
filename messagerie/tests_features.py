"""Parcours de la messagerie privée."""

from django.test import TestCase
from django.urls import reverse

from messagerie.models import PrivateMessage, PrivateMessageSubject
from users.models import User


class MessagerieFeatureTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username='alice', email='a@test.com', password='pass')
        cls.bob = User.objects.create_user(username='bob', email='b@test.com', password='pass')
        cls.eve = User.objects.create_user(username='eve', email='e@test.com', password='pass')

    def setUp(self):
        self.subject = PrivateMessageSubject.objects.create(
            sender=self.alice, receiver=self.bob, subject='Échange de jeux'
        )
        PrivateMessage.objects.create(subject=self.subject, author=self.alice, message='Tu as Zelda ?')

    def test_pages_require_login(self):
        for url in (reverse('pm_home'), reverse('pm_new'),
                    reverse('pm_view', args=[self.subject.id])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(reverse('pm_delete', args=[self.subject.id])).status_code, 302)
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)

    def test_inbox_lists_conversations_of_both_sides(self):
        for user in (self.alice, self.bob):
            self.client.force_login(user)
            self.assertContains(self.client.get(reverse('pm_home')), 'Échange de jeux')
        self.client.force_login(self.eve)
        self.assertNotContains(self.client.get(reverse('pm_home')), 'Échange de jeux')

    def test_send_new_message_redirects_to_conversation(self):
        # Décale les id des messages et des sujets pour détecter une confusion
        extra = PrivateMessageSubject.objects.create(sender=self.bob, receiver=self.eve, subject='x')
        for _ in range(3):
            PrivateMessage.objects.create(subject=extra, author=self.bob, message='x')

        self.client.force_login(self.alice)
        response = self.client.post(reverse('pm_new'), {
            'receiver': self.eve.id, 'subject': 'Salut Eve', 'message': 'Bonjour !',
        })
        subject = PrivateMessageSubject.objects.get(subject='Salut Eve')
        self.assertRedirects(response, reverse('pm_view', args=[subject.id]))
        self.assertEqual(subject.sender, self.alice)
        self.assertFalse(subject.is_read)
        self.assertEqual(subject.messages.get().message, 'Bonjour !')

    def test_cannot_message_yourself(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('pm_new'), {
            'receiver': self.alice.id, 'subject': 'Moi', 'message': 'Moi',
        })
        self.assertFalse(PrivateMessageSubject.objects.filter(subject='Moi').exists())

    def test_receiver_reading_marks_as_read(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse('pm_view', args=[self.subject.id])).status_code, 200)
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_read)

    def test_sender_reading_does_not_mark_as_read(self):
        self.client.force_login(self.alice)
        self.client.get(reverse('pm_view', args=[self.subject.id]))
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_read)

    def test_reply_in_conversation(self):
        self.client.force_login(self.bob)
        response = self.client.post(reverse('pm_view', args=[self.subject.id]), {'message': 'Oui !'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.subject.messages.filter(author=self.bob, message='Oui !').exists())
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_read)

    def test_stranger_cannot_read_or_reply(self):
        self.client.force_login(self.eve)
        response = self.client.post(reverse('pm_view', args=[self.subject.id]), {'message': 'Intrus'})
        self.assertRedirects(response, reverse('pm_home'))
        self.assertFalse(self.subject.messages.filter(author=self.eve).exists())

    def test_stranger_cannot_delete(self):
        self.client.force_login(self.eve)
        self.client.post(reverse('pm_delete', args=[self.subject.id]))
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)

    def test_delete_by_get_is_refused(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse('pm_delete', args=[self.subject.id])).status_code, 405)
        self.subject.refresh_from_db()
        self.assertTrue(self.subject.is_active)

    def test_participant_deletes_conversation(self):
        self.client.force_login(self.bob)
        self.client.post(reverse('pm_delete', args=[self.subject.id]))
        self.subject.refresh_from_db()
        self.assertFalse(self.subject.is_active)
        self.assertEqual(self.client.get(reverse('pm_view', args=[self.subject.id])).status_code, 302)

    def test_unknown_conversation_returns_404(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('pm_view', args=[999999])).status_code, 404)
        self.assertEqual(self.client.post(reverse('pm_delete', args=[999999])).status_code, 404)

    def test_mass_mailing_reserved_to_superusers(self):
        User.objects.create_user(username='RetroBot', password='pass')
        before = PrivateMessageSubject.objects.count()
        self.client.force_login(self.alice)
        self.client.get(reverse('pm_send_all_users'))
        self.assertEqual(PrivateMessageSubject.objects.count(), before)

    def test_mass_mailing_by_superuser(self):
        User.objects.create_user(username='RetroBot', password='pass')
        root = User.objects.create_superuser(username='root', email='r@test.com', password='pass')
        self.client.force_login(root)
        self.client.get(reverse('pm_send_all_users'))
        # Deux messages de bienvenue par membre
        self.assertEqual(
            PrivateMessageSubject.objects.filter(receiver=self.alice, sender__username='RetroBot').count(), 2
        )

    def test_private_message_html_escaped(self):
        PrivateMessage.objects.create(subject=self.subject, author=self.alice, message='<script>vol()</script>')
        self.client.force_login(self.bob)
        response = self.client.get(reverse('pm_view', args=[self.subject.id]))
        self.assertNotContains(response, '<script>vol()</script>')
