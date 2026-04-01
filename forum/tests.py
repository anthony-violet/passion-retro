from django.test import TestCase
from forum.models import Category, Forum, Topic
from users.models import User

class ForumModelsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            active=True
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            description='Description de test'
        )
        
        self.forum = Forum.objects.create(
            category=self.category,
            author=self.user,
            name='Test Forum',
            description='Description du forum'
        )
    
    def test_create_category(self):
        self.assertEqual(self.category.name, 'Test Category')
        self.assertEqual(self.category.description, 'Description de test')
        self.assertIsNotNone(self.category.created)
        self.assertIsNotNone(self.category.updated)
    
    def test_create_forum(self):
        self.assertEqual(self.forum.name, 'Test Forum')
        self.assertEqual(self.forum.category, self.category)
        self.assertEqual(self.forum.author, self.user)
    
    def test_create_topic(self):
        topic = Topic.objects.create(
            forum=self.forum,
            author=self.user,
            title='Test Topic'
        )
        
        self.assertEqual(topic.title, 'Test Topic')
        self.assertEqual(topic.forum, self.forum)
        self.assertEqual(topic.author, self.user)
        self.assertEqual(topic.state, 'open')  # État par défaut
    
    def test_topic_state_update(self):
        topic = Topic.objects.create(
            forum=self.forum,
            author=self.user,
            title='Test Topic'
        )
        
        topic.state = 'closed'
        topic.save()
        
        topic.refresh_from_db()
        self.assertEqual(topic.state, 'closed')

class ForumBasicTest(TestCase):
    def test_forum_app_exists(self):
        # Test basique pour vérifier que l'application forum est installée
        from django.apps import apps
        self.assertTrue(apps.is_installed('forum'))
    
    def test_forum_models_exist(self):
        # Vérifier que les modèles principaux existent
        from forum.models import Category, Forum, Topic, Post
        self.assertTrue(hasattr(Category, 'objects'))
        self.assertTrue(hasattr(Forum, 'objects'))
        self.assertTrue(hasattr(Topic, 'objects'))
        self.assertTrue(hasattr(Post, 'objects'))
