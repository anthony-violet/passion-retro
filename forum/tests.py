from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from forum.models import Category, Forum, Post, Topic, TopicRead
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


class ForumUnreadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='unreaduser',
            email='unread@test.com',
            password='testpass123',
            active=True,
        )
        self.category = Category.objects.create(
            name='Catégorie non lue',
            description='Description',
        )
        self.forum = Forum.objects.create(
            category=self.category,
            author=self.user,
            name='Forum non lu',
            description='Description',
        )
        self.old_topic = Topic.objects.create(
            forum=self.forum,
            author=self.user,
            title='Ancien sujet',
        )
        self.recent_topic = Topic.objects.create(
            forum=self.forum,
            author=self.user,
            title='Sujet récent',
        )
        now = timezone.now()
        self.old_post = Post.objects.create(
            topic=self.old_topic,
            author=self.user,
            content='Ancien message',
        )
        self.recent_post = Post.objects.create(
            topic=self.recent_topic,
            author=self.user,
            content='Message récent',
        )
        Post.objects.filter(pk=self.old_post.pk).update(
            created=now - timedelta(days=2)
        )
        Post.objects.filter(pk=self.recent_post.pk).update(created=now)
        self.client.force_login(self.user)

    def _forum_unread(self):
        response = self.client.get(reverse('forum_home'))
        return response.context['unread_topics'][self.forum.id]

    def test_forum_unread_when_new_post_after_last_read(self):
        read = TopicRead.objects.create(user=self.user, topic=self.old_topic)
        TopicRead.objects.filter(pk=read.pk).update(
            last_read=timezone.now() - timedelta(days=1)
        )

        self.assertTrue(self._forum_unread())

    def test_forum_read_when_recent_topic_read_even_if_old_topic_unread(self):
        TopicRead.objects.create(user=self.user, topic=self.recent_topic)

        self.assertFalse(self._forum_unread())

    def test_forum_unread_when_user_has_no_reads(self):
        self.assertTrue(self._forum_unread())

    def test_forum_read_for_anonymous_user(self):
        self.client.logout()

        self.assertFalse(self._forum_unread())

    def test_forum_read_when_no_posts(self):
        empty_forum = Forum.objects.create(
            category=self.category,
            author=self.user,
            name='Forum vide',
            description='Description',
        )

        response = self.client.get(reverse('forum_home'))

        self.assertFalse(response.context['unread_topics'][empty_forum.id])

    def test_topic_list_still_marks_old_topic_unread(self):
        TopicRead.objects.create(user=self.user, topic=self.recent_topic)

        response = self.client.get(
            reverse('topic_list', args=[self.forum.id])
        )

        self.assertFalse(response.context['unread_topics'][self.recent_topic.id])
        self.assertTrue(response.context['unread_topics'][self.old_topic.id])


class ForumSeoP0Test(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        self.user = User.objects.create_user(
            username='seo', email='seo@test.com', password='pass12345', active=True
        )
        self.moderator = User.objects.create_user(
            username='modo', email='modo@test.com', password='pass12345', active=True
        )
        self.moderator.groups.add(Group.objects.create(name='Modérateur'))
        category = Category.objects.create(name='Cat', description='d')
        self.forum = Forum.objects.create(category=category, author=self.user, name='F1', description='d')
        self.other = Forum.objects.create(category=category, author=self.user, name='F2', description='d')
        self.topic = Topic.objects.create(forum=self.forum, author=self.user, title='Sujet')
        Post.objects.create(topic=self.topic, author=self.user, content='Bonjour')

    def test_unknown_ids_return_404(self):
        self.assertEqual(self.client.get('/forum/999999/').status_code, 404)
        self.assertEqual(self.client.get(f'/forum/{self.forum.id}/999999/').status_code, 404)
        self.assertEqual(self.client.get('/users/profile/999999/').status_code, 404)

    def test_wrong_forum_id_redirects_permanently(self):
        response = self.client.get(f'/forum/{self.other.id}/{self.topic.id}/?page=2')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], f'/forum/{self.forum.id}/{self.topic.id}/?page=2')

    def test_canonical_drops_invalid_or_first_page(self):
        url = f'/forum/{self.forum.id}/{self.topic.id}/'
        for query in ('?page=1', '?page=zzz', '?page=01'):
            response = self.client.get(url + query)
            self.assertEqual(response.context['seo_canonical'], f'http://testserver{url}')
        response = self.client.get(url + '?page=3')
        self.assertEqual(response.context['seo_canonical'], f'http://testserver{url}?page=3')

    def test_deactivated_topic_is_hidden(self):
        self.client.force_login(self.moderator)
        self.client.get(f'/forum/{self.forum.id}/{self.topic.id}/deactivate/')
        self.topic.refresh_from_db()
        self.assertFalse(self.topic.active)
        url = f'/forum/{self.forum.id}/{self.topic.id}/'
        self.assertEqual(self.client.get(url).status_code, 200)  # modérateur
        self.assertIn(self.topic, list(self.client.get(f'/forum/{self.forum.id}/').context['topics']))
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotIn(self.topic, list(self.client.get(f'/forum/{self.forum.id}/').context['topics']))
        self.assertNotIn(url, self.client.get('/sitemap.xml').content.decode())

    def test_news_topic_canonical_points_to_article(self):
        from posts.models import Post as Article
        Article.objects.create(
            title='Actu', slug='actu', content='x', type='news', active=True,
            author=self.user, forum_link=f'forum/{self.forum.id}/{self.topic.id}/',
        )
        response = self.client.get(f'/forum/{self.forum.id}/{self.topic.id}/')
        self.assertEqual(response.context['seo_canonical'], 'http://testserver/posts/actu/')


class SiteUrlNormalizationTest(TestCase):
    def test_normalize(self):
        from passion_retro.settings import _normalize_site_url as n
        self.assertEqual(n('127.0.0.1'), 'http://127.0.0.1')
        self.assertEqual(n('localhost:5500/'), 'http://localhost:5500')
        self.assertEqual(n('nostalgeek.fr'), 'https://nostalgeek.fr')
        self.assertEqual(n('https://nostalgeek.fr/'), 'https://nostalgeek.fr')
        self.assertEqual(n(''), 'http://localhost:5500')
