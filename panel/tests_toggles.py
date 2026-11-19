"""Les boutons de bascule du panel n'agissent qu'en POST."""

from django.test import TestCase
from django.urls import reverse

from forum.models import Category, Forum, Post, Topic
from guestbook.models import Guestbook
from users.models import User


class PanelTogglesPostOnlyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username='staff', password='p', is_staff=True)
        cls.member = User.objects.create_user(username='membre', password='p', active=True)
        forum = Forum.objects.create(
            category=Category.objects.create(name='C', description='d'),
            author=cls.staff, name='F', description='d',
        )
        cls.topic = Topic.objects.create(forum=forum, author=cls.member, title='T')
        cls.post = Post.objects.create(topic=cls.topic, author=cls.member, content='x')
        cls.entry = Guestbook.objects.create(author='A', content='B')

    def setUp(self):
        self.client.force_login(self.staff)

    def routes(self):
        return [
            ('panel_forum_topic_toggle', self.topic.id, 'panel_forum_topics'),
            ('panel_forum_post_toggle', self.post.id, 'panel_forum_posts'),
            ('panel_user_toggle', self.member.id, 'panel_user_list'),
            ('panel_guestbook_toggle', self.entry.id, 'panel_guestbook'),
        ]

    def test_get_refused(self):
        for name, pk, _ in self.routes():
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 405)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.state, 'open')

    def test_post_toggles(self):
        self.client.post(reverse('panel_forum_topic_toggle', args=[self.topic.id]))
        self.client.post(reverse('panel_forum_post_toggle', args=[self.post.id]))
        self.client.post(reverse('panel_user_toggle', args=[self.member.id]))
        self.client.post(reverse('panel_guestbook_toggle', args=[self.entry.id]))
        for obj in (self.topic, self.post, self.member, self.entry):
            obj.refresh_from_db()
        self.assertEqual(self.topic.state, 'closed')
        self.assertFalse(self.post.active)
        self.assertFalse(self.member.active)
        self.assertFalse(self.entry.active)

    def test_list_pages_render_forms(self):
        for name, pk, page in self.routes():
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertContains(response, f'action="{reverse(name, args=[pk])}"')
                self.assertNotContains(response, f'href="{reverse(name, args=[pk])}"')
