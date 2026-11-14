from django.test import TestCase
from django.urls import reverse
from forum.models import Category, Forum, Post, Topic
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


class ForumLevelDisplayTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='forumlevel',
            email='forumlevel@test.com',
            password='testpass123',
            active=True,
        )
        self.user.levels.create(level=12, experience=0)
        self.category = Category.objects.create(
            name='Catégorie niveau',
            description='Description',
        )
        self.forum = Forum.objects.create(
            category=self.category,
            author=self.user,
            name='Forum niveau',
            description='Description',
        )
        self.topic = Topic.objects.create(
            forum=self.forum,
            author=self.user,
            title='Sujet niveau',
        )
        self.post = Post.objects.create(
            topic=self.topic,
            author=self.user,
            content='Message de test',
        )
        self.client.login(username='forumlevel', password='testpass123')

    def test_topic_list_does_not_display_level_badge(self):
        response = self.client.get(
            reverse('topic_list', args=[self.forum.id])
        )

        self.assertNotContains(response, 'level-badge')
        self.assertNotContains(response, 'LVL')
        self.assertNotContains(response, 'Aventurier')

    def test_forum_home_does_not_display_level_badge(self):
        response = self.client.get(reverse('forum_home'))

        self.assertNotContains(response, 'level-badge')
        self.assertNotContains(response, 'LVL')

    def test_topic_detail_displays_level_badge_in_user_info(self):
        response = self.client.get(
            reverse('post_list', args=[self.forum.id, self.topic.id])
        )

        self.assertContains(response, 'forum-avatar-wrap')
        self.assertContains(response, 'forum-level-title')
        self.assertContains(response, 'level-badge')
        self.assertContains(response, 'LVL')
        self.assertContains(response, '>12<')
        self.assertContains(response, 'Aventurier')
