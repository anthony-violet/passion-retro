import importlib
from datetime import timedelta

from django.apps import apps as global_apps
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from forum.models import Category as ForumCategory, Forum, Post as ForumPost, Topic, TopicSubscription
from posts.models import Category, Post
from posts.news import NEWS_FORUM_NAME, latest_reactions, news_queryset, publish_news
from users.models import User


class NewsTestMixin:
    def setUp(self):
        self.author = User.objects.create_user(username='redac', email='r@test.com', password='pass12345')
        self.reader = User.objects.create_user(username='lecteur', email='l@test.com', password='pass12345')
        self.staff = User.objects.create_user(username='modo', email='m@test.com', password='pass12345', is_staff=True)
        self.category = Category.objects.create(name='Actualités')
        forum_cat = ForumCategory.objects.create(name='Site', description='x')
        self.forum = Forum.objects.create(category=forum_cat, author=self.staff, name=NEWS_FORUM_NAME, description='x')

    def make_news(self, title='Une cartouche retrouvée', active=True, **kwargs):
        post = Post.objects.create(
            title=title, slug=slugify(title), content='Contenu [b]rétro[/b]',
            type='news', author=self.author, category=self.category, active=active, **kwargs,
        )
        publish_news(post)
        post.refresh_from_db()
        return post

    def xp(self, user):
        user.refresh_from_db()
        return user.experience


class PublishNewsTest(NewsTestMixin, TestCase):
    def test_active_news_gets_topic_and_publication_date(self):
        post = self.make_news(forum_prompt='Et vous, vous l’aviez ?')
        self.assertIsNotNone(post.topic)
        self.assertIsNotNone(post.published_at)
        self.assertEqual(post.topic.forum, self.forum)
        self.assertEqual(post.forum_link, f'forum/{self.forum.id}/{post.topic.id}/')
        opening = post.topic.posts.get()
        self.assertIn('Et vous, vous l’aviez ?', opening.content)
        self.assertIn(reverse('view_post', args=[post.slug]), opening.content)
        self.assertEqual(self.xp(self.author), 20)

    def test_inactive_news_has_no_topic(self):
        post = self.make_news(active=False)
        self.assertIsNone(post.topic)
        self.assertIsNone(post.published_at)
        self.assertEqual(Topic.objects.count(), 0)

    def test_publish_is_idempotent(self):
        post = self.make_news()
        publish_news(post)
        publish_news(post)
        self.assertEqual(Topic.objects.count(), 1)
        self.assertEqual(self.xp(self.author), 20)

    def test_long_title_is_truncated_for_topic(self):
        post = self.make_news(title='T' * 120)
        self.assertLessEqual(len(post.topic.title), 50)

    def test_create_post_inactive_then_panel_approval_creates_topic(self):
        group = Group.objects.create(name='Rédacteur')
        self.author.groups.add(group)
        self.client.login(username='redac', password='pass12345')
        self.client.post(reverse('create_news', args=['news']), {
            'title': 'Brouillon', 'content': 'Texte', 'forum_prompt': 'Votre avis ?',
            'source_url': 'https://exemple.fr/source',
        })
        post = Post.objects.get(title='Brouillon')
        self.assertIsNone(post.topic)
        self.assertEqual(post.forum_prompt, 'Votre avis ?')

        self.client.login(username='modo', password='pass12345')
        self.client.post(reverse('panel_post_approve', args=[post.id]))
        post.refresh_from_db()
        self.assertTrue(post.active)
        self.assertIsNotNone(post.topic)
        self.assertIsNotNone(post.published_at)

    def test_create_post_rejects_invalid_source_url(self):
        group = Group.objects.create(name='Rédacteur')
        self.author.groups.add(group)
        self.client.login(username='redac', password='pass12345')
        response = self.client.post(reverse('create_news', args=['news']), {
            'title': 'Source cassée', 'content': 'Texte', 'source_url': 'pas une url',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(title='Source cassée').exists())


class NewsReactionTest(NewsTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.post = self.make_news()
        self.url = reverse('news_react', args=[self.post.slug])

    def test_reaction_posts_in_forum_topic_with_first_bonus(self):
        self.client.login(username='lecteur', password='pass12345')
        response = self.client.post(self.url, {'content': 'Super trouvaille !', 'subscribe': 'on'})
        self.assertRedirects(response, reverse('view_post', args=[self.post.slug]) + '#discussion',
                             fetch_redirect_response=False)
        self.assertTrue(ForumPost.objects.filter(topic=self.post.topic, author=self.reader,
                                                 content='Super trouvaille !').exists())
        self.assertTrue(TopicSubscription.objects.get(user=self.reader, topic=self.post.topic).active)
        self.assertEqual(self.xp(self.reader), 15)

        self.client.post(self.url, {'content': 'Encore moi'})
        self.assertEqual(self.xp(self.reader), 25)
        self.assertFalse(TopicSubscription.objects.get(user=self.reader, topic=self.post.topic).active)

    def test_reaction_requires_login(self):
        response = self.client.post(self.url, {'content': 'Coucou'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ForumPost.objects.filter(topic=self.post.topic).count(), 1)

    def test_empty_reaction_is_refused(self):
        self.client.login(username='lecteur', password='pass12345')
        self.client.post(self.url, {'content': '   '})
        self.assertEqual(ForumPost.objects.filter(topic=self.post.topic).count(), 1)

    def test_locked_topic_refuses_reactions(self):
        Topic.objects.filter(pk=self.post.topic_id).update(state='closed')
        self.client.login(username='lecteur', password='pass12345')
        self.client.post(self.url, {'content': 'Trop tard'})
        self.assertEqual(ForumPost.objects.filter(topic=self.post.topic).count(), 1)

    def test_reaction_count_excludes_opening_message(self):
        ForumPost.objects.create(topic=self.post.topic, author=self.reader, content='Un')
        ForumPost.objects.create(topic=self.post.topic, author=self.reader, content='Deux')
        ForumPost.objects.create(topic=self.post.topic, author=self.reader, content='Masqué', active=False)
        annotated = news_queryset().get(pk=self.post.pk)
        self.assertEqual(annotated.reactions, 2)
        self.assertEqual([r.content for r in latest_reactions(self.post)], ['Un', 'Deux'])

    def test_detail_page_shows_discussion(self):
        ForumPost.objects.create(topic=self.post.topic, author=self.reader, content='Je l’avais !')
        self.client.login(username='lecteur', password='pass12345')
        response = self.client.get(reverse('view_post', args=[self.post.slug]))
        self.assertContains(response, 'La discussion')
        self.assertContains(response, 'Je l’avais !')
        self.assertContains(response, self.url)
        self.assertContains(response, '+10 XP')  # déjà réagi : plus de bonus


class NewsPagesTest(NewsTestMixin, TestCase):
    def test_home_prefers_featured_news(self):
        featured = self.make_news(title='A la une', featured=True)
        Post.objects.filter(pk=featured.pk).update(published_at=timezone.now() - timedelta(days=5))
        self.make_news(title='Plus recente')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['featured_news'].pk, featured.pk)
        self.assertEqual([n.title for n in response.context['news_cards']], ['Plus recente'])

    def test_home_author_decoration_is_the_authors(self):
        self.author.username_decoration = 'deco-auteur'
        self.author.save()
        self.reader.username_decoration = 'deco-visiteur'
        self.reader.save()
        self.make_news()
        self.client.login(username='lecteur', password='pass12345')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'deco-auteur')
        self.assertNotContains(response, 'class="news-author deco-visiteur"')

    def test_list_filters_by_category_and_sorts_by_reactions(self):
        other = Category.objects.create(name='Arcade')
        calm = self.make_news(title='Calme')
        busy = self.make_news(title='Animee')
        Post.objects.filter(pk=busy.pk).update(category=other)
        for i in range(3):
            ForumPost.objects.create(topic=busy.topic, author=self.reader, content=str(i))

        response = self.client.get(reverse('news_list'), {'cat': other.pk})
        self.assertEqual([p.title for p in response.context['news']], ['Animee'])

        response = self.client.get(reverse('news_list'), {'tri': 'commentees'})
        self.assertEqual([p.title for p in response.context['news']], ['Animee', 'Calme'])
        self.assertTrue(response.context['seo_noindex'])
        self.assertEqual(calm.category, self.category)


class BackfillMigrationTest(NewsTestMixin, TestCase):
    def test_forum_link_is_converted_to_topic(self):
        topic = Topic.objects.create(title='Ancienne', forum=self.forum, author=self.author)
        post = Post.objects.create(
            title='Ancienne', slug='ancienne', content='x', type='news', author=self.author,
            category=self.category, active=True, forum_link=f'forum/{self.forum.id}/{topic.id}/',
        )
        broken = Post.objects.create(
            title='Cassée', slug='cassee', content='x', type='news', author=self.author,
            category=self.category, active=True, forum_link='forum/1/999999/',
        )
        migration = importlib.import_module('posts.migrations.0019_backfill_news_topic')
        migration.backfill(global_apps, None)
        post.refresh_from_db()
        broken.refresh_from_db()
        self.assertEqual(post.topic, topic)
        self.assertEqual(post.published_at, post.created)
        self.assertIsNone(broken.topic)
