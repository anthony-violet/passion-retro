"""Parcours fonctionnels du forum : création, réponses, édition, modération,
verrouillage, abonnements et pagination."""

from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from forum.models import Category, Forum, Post, Topic, TopicRead, TopicSubscription
from users.models import User


class ForumFeatureBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username='auteur', email='auteur@test.com', password='pass', active=True
        )
        cls.member = User.objects.create_user(
            username='membre', email='membre@test.com', password='pass', active=True
        )
        cls.moderator = User.objects.create_user(
            username='modo', email='modo@test.com', password='pass', active=True
        )
        cls.moderator.groups.add(Group.objects.create(name='Modérateur'))
        cls.admin = User.objects.create_user(
            username='admin', email='admin@test.com', password='pass', active=True
        )
        cls.admin.groups.add(Group.objects.create(name='Super Admin'))

        category = Category.objects.create(name='Jeux', description='Desc')
        cls.forum = Forum.objects.create(
            category=category, author=cls.admin, name='Consoles', description='Desc'
        )
        cls.other_forum = Forum.objects.create(
            category=category, author=cls.admin, name='Micro', description='Desc'
        )

    def setUp(self):
        self.topic = Topic.objects.create(forum=self.forum, author=self.author, title='Ma NES')
        self.first_post = Post.objects.create(
            topic=self.topic, author=self.author, content='Premier message'
        )

    def topic_url(self, topic=None):
        topic = topic or self.topic
        return reverse('post_list', args=[topic.forum_id, topic.id])


class CreateTopicTest(ForumFeatureBase):
    def url(self):
        return reverse('create_topic', args=[self.forum.id])

    def test_requires_login(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login', response['Location'])

    def test_create_topic_with_first_post(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), {
            'title': 'Ma Megadrive', 'content': 'Elle marche encore', 'subscribe': 'on',
        })
        topic = Topic.objects.get(title='Ma Megadrive')
        self.assertRedirects(response, self.topic_url(topic))
        self.assertEqual(topic.author, self.member)
        self.assertEqual(topic.state, 'open')
        self.assertEqual(topic.posts.get().content, 'Elle marche encore')
        self.assertTrue(TopicSubscription.objects.get(user=self.member, topic=topic).active)

    def test_create_topic_without_subscription(self):
        self.client.force_login(self.member)
        self.client.post(self.url(), {'title': 'Sans abo', 'content': 'Texte'})
        topic = Topic.objects.get(title='Sans abo')
        self.assertFalse(TopicSubscription.objects.get(user=self.member, topic=topic).active)

    def test_creating_topic_grants_experience(self):
        self.client.force_login(self.member)
        before = self.member.experience
        self.client.post(self.url(), {'title': 'XP', 'content': 'Texte'})
        self.member.refresh_from_db()
        self.assertGreater(self.member.experience, before)

    def test_missing_fields_redisplay_form(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), {'title': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Topic.objects.filter(author=self.member).exists())

    def test_title_longer_than_model_limit_is_rejected(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), {'title': 'x' * 51, 'content': 'Texte'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Topic.objects.filter(author=self.member).exists())

    def test_unknown_forum_returns_404(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('create_topic', args=[999999]))
        self.assertEqual(response.status_code, 404)


class ReplyTest(ForumFeatureBase):
    def test_member_can_reply(self):
        self.client.force_login(self.member)
        response = self.client.post(self.topic_url(), {'content': 'Belle console !'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.topic.posts.filter(author=self.member, content='Belle console !').exists())
        self.assertContains(response, 'Belle console !')

    def test_anonymous_cannot_reply(self):
        response = self.client.post(self.topic_url(), {'content': 'Spam'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.topic.posts.count(), 1)

    def test_empty_reply_is_rejected(self):
        self.client.force_login(self.member)
        self.client.post(self.topic_url(), {'content': ''})
        self.assertEqual(self.topic.posts.count(), 1)

    def test_cannot_reply_to_locked_topic(self):
        self.topic.state = 'closed'
        self.topic.save()
        self.client.force_login(self.member)
        response = self.client.post(self.topic_url(), {'content': 'Je force'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.topic.posts.count(), 1)

    def test_moderator_can_reply_to_locked_topic(self):
        self.topic.state = 'closed'
        self.topic.save()
        self.client.force_login(self.moderator)
        self.client.post(self.topic_url(), {'content': 'Note de modération'})
        self.assertEqual(self.topic.posts.count(), 2)

    def test_reply_notifies_subscribers_but_not_author(self):
        TopicSubscription.objects.create(user=self.author, topic=self.topic, active=True)
        TopicSubscription.objects.create(user=self.member, topic=self.topic, active=True)
        self.client.force_login(self.member)
        self.client.post(self.topic_url(), {'content': 'Réponse', 'subscribe': 'on'})
        recipients = [address for message in mail.outbox for address in message.to]
        self.assertIn(self.author.email, recipients)
        self.assertNotIn(self.member.email, recipients)

    def test_inactive_subscription_is_not_notified(self):
        TopicSubscription.objects.create(user=self.author, topic=self.topic, active=False)
        self.client.force_login(self.member)
        self.client.post(self.topic_url(), {'content': 'Réponse'})
        self.assertEqual(len(mail.outbox), 0)

    def test_viewing_topic_increments_views_and_marks_read(self):
        self.client.force_login(self.member)
        self.client.get(self.topic_url())
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.views, 1)
        self.assertTrue(TopicRead.objects.filter(user=self.member, topic=self.topic).exists())

    def test_pagination_twenty_posts_per_page(self):
        Post.objects.bulk_create([
            Post(topic=self.topic, author=self.author, content=f'Message {i}')
            for i in range(25)
        ])
        page2 = self.client.get(self.topic_url(), {'page': 2})
        self.assertEqual(page2.status_code, 200)
        self.assertEqual(len(page2.context['posts']), 6)
        self.assertTrue(page2.context['is_paginated'])

    def test_deactivated_post_is_hidden(self):
        hidden = Post.objects.create(topic=self.topic, author=self.member, content='Message masqué')
        hidden.active = False
        hidden.save()
        response = self.client.get(self.topic_url())
        self.assertNotContains(response, 'Message masqué')


class EditPostTest(ForumFeatureBase):
    def url(self):
        return reverse('forum_edit_post', args=[self.first_post.id])

    def test_author_can_edit(self):
        self.client.force_login(self.author)
        response = self.client.post(self.url(), {'content': 'Corrigé'})
        self.assertRedirects(response, self.topic_url())
        self.first_post.refresh_from_db()
        self.assertEqual(self.first_post.content, 'Corrigé')

    def test_other_member_cannot_edit(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), {'content': 'Piraté'})
        self.assertEqual(response.status_code, 403)
        self.first_post.refresh_from_db()
        self.assertEqual(self.first_post.content, 'Premier message')

    def test_admin_can_edit(self):
        self.client.force_login(self.admin)
        self.client.post(self.url(), {'content': 'Modéré'})
        self.first_post.refresh_from_db()
        self.assertEqual(self.first_post.content, 'Modéré')

    def test_moderator_can_edit(self):
        self.client.force_login(self.moderator)
        self.client.post(self.url(), {'content': 'Modéré'})
        self.first_post.refresh_from_db()
        self.assertEqual(self.first_post.content, 'Modéré')

    def test_edit_form_prefilled(self):
        self.client.force_login(self.author)
        response = self.client.get(self.url())
        self.assertContains(response, 'Premier message')

    def test_empty_content_rejected(self):
        self.client.force_login(self.author)
        response = self.client.post(self.url(), {'content': ''})
        self.assertEqual(response.status_code, 200)
        self.first_post.refresh_from_db()
        self.assertEqual(self.first_post.content, 'Premier message')


class ModerationTest(ForumFeatureBase):
    MODERATION_ROUTES = [
        ('lock_topic', lambda self: [self.topic.id]),
        ('unlock_topic', lambda self: [self.topic.id]),
        ('deactivate_topic', lambda self: [self.forum.id, self.topic.id]),
        ('activate_topic', lambda self: [self.forum.id, self.topic.id]),
        ('deactivate_post', lambda self: [self.first_post.id]),
        ('activate_post', lambda self: [self.first_post.id]),
    ]

    def test_members_cannot_moderate(self):
        self.client.force_login(self.member)
        for name, args in self.MODERATION_ROUTES:
            with self.subTest(route=name):
                response = self.client.post(reverse(name, args=args(self)))
                self.assertEqual(response.status_code, 403)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.state, 'open')
        self.assertTrue(self.topic.active)

    def test_anonymous_redirected_to_login(self):
        for name, args in self.MODERATION_ROUTES:
            with self.subTest(route=name):
                response = self.client.post(reverse(name, args=args(self)))
                self.assertEqual(response.status_code, 302)

    def test_get_requests_are_refused(self):
        self.client.force_login(self.moderator)
        for name, args in self.MODERATION_ROUTES:
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args(self)))
                self.assertEqual(response.status_code, 405)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.state, 'open')
        self.assertTrue(self.topic.active)

    def test_administrateur_group_can_moderate(self):
        admin = User.objects.create_user(username='administrateur', password='pass')
        admin.groups.add(Group.objects.get_or_create(name='Administrateur')[0])
        self.client.force_login(admin)
        self.client.post(reverse('lock_topic', args=[self.topic.id]))
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.state, 'closed')

    def test_moderation_buttons_are_post_forms(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self.topic_url())
        self.assertContains(response, f'action="{reverse("lock_topic", args=[self.topic.id])}"')
        self.assertContains(response, f'action="{reverse("deactivate_post", args=[self.first_post.id])}"')
        self.assertNotContains(response, f'href="{reverse("lock_topic", args=[self.topic.id])}"')

    def test_moderation_buttons_hidden_from_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.topic_url())
        self.assertNotContains(response, reverse('lock_topic', args=[self.topic.id]))
        self.assertNotContains(response, reverse('deactivate_post', args=[self.first_post.id]))

    def test_lock_and_unlock(self):
        self.client.force_login(self.moderator)
        self.client.post(reverse('lock_topic', args=[self.topic.id]))
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.state, 'closed')
        self.client.post(reverse('unlock_topic', args=[self.topic.id]))
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.state, 'open')

    def test_deactivate_topic_hides_it_from_members(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('deactivate_topic', args=[self.forum.id, self.topic.id]))
        self.assertRedirects(response, reverse('topic_list', args=[self.forum.id]))
        self.topic.refresh_from_db()
        self.assertFalse(self.topic.active)

        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.topic_url()).status_code, 404)
        listing = self.client.post(reverse('topic_list', args=[self.forum.id]))
        self.assertNotContains(listing, 'Ma NES')

        # Les modérateurs voient toujours le sujet désactivé
        self.client.force_login(self.moderator)
        self.assertEqual(self.client.get(self.topic_url()).status_code, 200)

    def test_reactivate_topic(self):
        self.topic.active = False
        self.topic.save()
        self.client.force_login(self.moderator)
        self.client.post(reverse('activate_topic', args=[self.forum.id, self.topic.id]))
        self.topic.refresh_from_db()
        self.assertTrue(self.topic.active)

    def test_deactivate_and_reactivate_post(self):
        self.client.force_login(self.moderator)
        self.client.post(reverse('deactivate_post', args=[self.first_post.id]))
        self.first_post.refresh_from_db()
        self.assertFalse(self.first_post.active)
        self.client.post(reverse('activate_post', args=[self.first_post.id]))
        self.first_post.refresh_from_db()
        self.assertTrue(self.first_post.active)

    def test_moderation_on_unknown_ids_returns_404(self):
        self.client.force_login(self.moderator)
        for name in ('lock_topic', 'unlock_topic', 'deactivate_post', 'activate_post'):
            with self.subTest(route=name):
                self.assertEqual(self.client.post(reverse(name, args=[999999])).status_code, 404)


class TopicListingTest(ForumFeatureBase):
    def test_forum_home_lists_categories_forums_and_counts(self):
        response = self.client.get(reverse('forum_home'))
        self.assertContains(response, 'Jeux')
        self.assertContains(response, 'Consoles')
        self.assertEqual(response.context['count_topics'][self.forum.id], 1)
        self.assertEqual(response.context['last_posts'][self.forum.id], self.first_post)
        self.assertIsNone(response.context['last_posts'][self.other_forum.id])

    def test_topic_list_sorted_by_last_activity(self):
        recent = Topic.objects.create(forum=self.forum, author=self.member, title='Récent')
        Post.objects.create(topic=recent, author=self.member, content='Nouveau')
        response = self.client.get(reverse('topic_list', args=[self.forum.id]))
        titles = [topic.title for topic in response.context['topics']]
        self.assertEqual(titles, ['Récent', 'Ma NES'])

    def test_topic_list_paginated_by_twenty(self):
        for i in range(21):
            topic = Topic.objects.create(forum=self.forum, author=self.member, title=f'Sujet {i}')
            Post.objects.create(topic=topic, author=self.member, content='x')
        response = self.client.get(reverse('topic_list', args=[self.forum.id]))
        self.assertEqual(len(response.context['topics']), 20)
        response = self.client.get(reverse('topic_list', args=[self.forum.id]), {'page': 2})
        self.assertEqual(len(response.context['topics']), 2)

    def test_last_post_page_number(self):
        Post.objects.bulk_create([
            Post(topic=self.topic, author=self.author, content=f'M{i}') for i in range(20)
        ])
        response = self.client.get(reverse('topic_list', args=[self.forum.id]))
        self.assertEqual(response.context['page_numbers'][self.topic.id], 2)

    def test_invalid_page_number_falls_back(self):
        response = self.client.get(reverse('topic_list', args=[self.forum.id]), {'page': 'abc'})
        self.assertEqual(response.status_code, 200)


class UnsubscribeTest(ForumFeatureBase):
    def test_unsubscribe_link_without_login(self):
        subscription = TopicSubscription.objects.create(user=self.member, topic=self.topic)
        url = reverse('unsubscribe_topic', args=[subscription.token])
        self.assertEqual(self.client.get(url).status_code, 200)
        subscription.refresh_from_db()
        self.assertTrue(subscription.active, "Un GET ne doit pas désabonner")
        self.client.post(url)
        subscription.refresh_from_db()
        self.assertFalse(subscription.active)

    def test_reply_with_subscribe_unchecked_unsubscribes(self):
        TopicSubscription.objects.create(user=self.member, topic=self.topic, active=True)
        self.client.force_login(self.member)
        self.client.post(self.topic_url(), {'content': 'Je pars'})
        self.assertFalse(TopicSubscription.objects.get(user=self.member, topic=self.topic).active)


class ForumXssTest(ForumFeatureBase):
    def test_member_html_escaped_in_topic(self):
        Post.objects.create(topic=self.topic, author=self.member, content='<script>alert("xss")</script>')
        response = self.client.get(self.topic_url())
        self.assertNotContains(response, '<script>alert("xss")</script>')

    def test_member_biography_escaped(self):
        self.author.biography = '<img src=x onerror=alert(1)>'
        self.author.save()
        response = self.client.get(self.topic_url())
        self.assertNotContains(response, '<img src=x onerror=alert(1)>')

    def test_staff_html_kept(self):
        staff = User.objects.create_user(username='redac', password='p', is_staff=True)
        Post.objects.create(topic=self.topic, author=staff, content='<center>Annonce</center>')
        self.assertContains(self.client.get(self.topic_url()), '<center>Annonce</center>')
