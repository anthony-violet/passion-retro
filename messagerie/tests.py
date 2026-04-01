from django.test import TestCase
from messagerie.models import PrivateMessageSubject, PrivateMessage
from users.models import User

class MessagerieModelsTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username='sender',
            email='sender@test.com',
            password='testpass123',
            active=True
        )
        
        self.receiver = User.objects.create_user(
            username='receiver',
            email='receiver@test.com',
            password='testpass123',
            active=True
        )
        
        self.subject = PrivateMessageSubject.objects.create(
            sender=self.sender,
            receiver=self.receiver,
            subject='Sujet de test',
            is_read=False,
            is_active=True
        )
        
        self.message = PrivateMessage.objects.create(
            subject=self.subject,
            author=self.sender,
            message='Contenu du message de test'
        )
    
    def test_create_message_subject(self):
        self.assertEqual(self.subject.subject, 'Sujet de test')
        self.assertEqual(self.subject.sender, self.sender)
        self.assertEqual(self.subject.receiver, self.receiver)
        self.assertFalse(self.subject.is_read)
        self.assertTrue(self.subject.is_active)
    
    def test_create_message(self):
        self.assertEqual(self.message.message, 'Contenu du message de test')
        self.assertEqual(self.message.subject, self.subject)
        self.assertEqual(self.message.author, self.sender)
        self.assertIsNotNone(self.message.date_sent)
    
    def test_message_subject_string_representation(self):
        expected = f'Sujet: {self.subject.subject} (De: {self.sender.username} À: {self.receiver.username})'
        self.assertEqual(str(self.subject), expected)
    
    def test_message_string_representation(self):
        expected = f'{self.sender.username} ({self.message.date_sent})'
        self.assertEqual(str(self.message), expected)

class MessagerieBasicTest(TestCase):
    def test_messagerie_app_exists(self):
        # Test basique pour vérifier que l'application messagerie est installée
        from django.apps import apps
        self.assertTrue(apps.is_installed('messagerie'))
    
    def test_message_models_exist(self):
        # Vérifier que les modèles principaux existent
        self.assertTrue(hasattr(PrivateMessageSubject, 'objects'))
        self.assertTrue(hasattr(PrivateMessage, 'objects'))
