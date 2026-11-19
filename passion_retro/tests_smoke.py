"""Test de fumée : parcourt toutes les URL du site et vérifie qu'aucune ne plante.

Chaque route est appelée en GET par trois profils (visiteur, membre, staff
« Super Admin »). Les paramètres numériques pointent vers des objets
inexistants : une route robuste doit répondre 404 / 302 / 403, jamais 500.
Les pages de liste sont aussi rendues avec du contenu réel en base.
"""

import uuid

from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from forum.models import Category as ForumCategory, Forum, Post as ForumPost, Topic
from guestbook.models import Guestbook
from messagerie.models import PrivateMessage, PrivateMessageSubject
from users.models import User

MISSING_ID = 987654

# Routes qui ne se testent pas en GET générique (fichiers, médias, admin).
SKIPPED_NAMES = {None, 'logout'}

# Valeurs des paramètres textuels par nom d'argument.
STR_KWARGS = {
    'slug': 'slug-inexistant',
    'type': 'news',
    'party_id': 'partie-inexistante',
    'user_id': '987654',
    'theme_name': 'theme-inexistant',
    'key': 'cle-inexistante',
    'uidb64': 'AA',
    'token': 'jeton-invalide',
}


def iter_patterns(patterns, namespace=''):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            if 'admin' in str(entry.pattern):
                continue
            child_ns = namespace
            if entry.namespace:
                child_ns = f"{namespace}{entry.namespace}:"
            yield from iter_patterns(entry.url_patterns, child_ns)
        elif isinstance(entry, URLPattern):
            yield namespace, entry


def build_kwargs(pattern):
    kwargs = {}
    for name, converter in pattern.pattern.converters.items():
        type_name = type(converter).__name__
        if type_name == 'IntConverter':
            kwargs[name] = MISSING_ID
        elif type_name == 'UUIDConverter':
            kwargs[name] = uuid.uuid4()
        elif type_name == 'SlugConverter':
            kwargs[name] = STR_KWARGS.get(name, 'slug-inexistant')
        else:
            kwargs[name] = STR_KWARGS.get(name, 'inexistant')
    return kwargs


def all_named_routes():
    routes = []
    seen = set()
    for namespace, pattern in iter_patterns(get_resolver().url_patterns):
        if pattern.name in SKIPPED_NAMES:
            continue
        full_name = namespace + pattern.name
        if full_name in seen or pattern.pattern.regex.pattern.startswith('^media'):
            continue
        seen.add(full_name)
        routes.append((full_name, pattern))
    return routes


class SmokeFixturesMixin:
    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user(
            username='membre', email='membre@test.com', password='testpass123'
        )
        cls.other = User.objects.create_user(
            username='autre', email='autre@test.com', password='testpass123'
        )
        cls.staff = User.objects.create_user(
            username='staff', email='staff@test.com', password='testpass123',
            is_staff=True, is_superuser=True,
        )
        cls.staff.groups.add(Group.objects.get_or_create(name='Super Admin')[0])

        category = ForumCategory.objects.create(name='Général', description='Desc')
        cls.forum = Forum.objects.create(
            category=category, author=cls.staff, name='Discussions', description='Desc'
        )
        cls.topic = Topic.objects.create(forum=cls.forum, author=cls.member, title='Bonjour')
        ForumPost.objects.create(topic=cls.topic, author=cls.member, content='[b]Salut[/b]')

        Guestbook.objects.create(author='Visiteur', content='Super site')

        subject = PrivateMessageSubject.objects.create(
            sender=cls.other, receiver=cls.member, subject='Coucou'
        )
        PrivateMessage.objects.create(subject=subject, author=cls.other, message='Hello')


class AllRoutesSmokeTest(SmokeFixturesMixin, TestCase):
    """Aucune route ne doit renvoyer d'erreur 500, quel que soit le profil."""

    def _check_all_routes(self, user=None):
        client = Client(raise_request_exception=False)
        if user:
            client.force_login(user)
        routes = all_named_routes()
        self.assertGreater(len(routes), 150)
        for full_name, pattern in routes:
            kwargs = build_kwargs(pattern)
            url = reverse(full_name, kwargs=kwargs)
            with self.subTest(route=full_name, url=url):
                response = client.get(url)
                self.assertLess(
                    response.status_code, 500,
                    f"{url} → {response.status_code}",
                )

    def test_routes_as_anonymous(self):
        self._check_all_routes()

    def test_routes_as_member(self):
        self._check_all_routes(self.member)

    def test_routes_as_staff(self):
        self._check_all_routes(self.staff)


class MainPagesRenderTest(SmokeFixturesMixin, TestCase):
    """Les pages principales s'affichent (200) avec du contenu en base."""

    PUBLIC_PAGES = [
        'home', 'discover', 'news_list', 'forum_home', 'guestbook_home',
        'home_gallery', 'portal_games', 'quiz_home', 'shop_home',
        'history_versions_home', 'ephemerides:ephemerides_today',
        'wall_memories:wall', 'announcement',
        'robots_txt', 'llms_txt', 'sitemap', 'login', 'register',
    ]
    MEMBER_PAGES = [
        'profile', 'profile_update', 'contributions', 'contribute', 'pm_home',
        'pm_new', 'unread_topic_list', 'wall_memories:mine',
        'wall_memories:favorites', 'wall_memories:create',
    ]
    STAFF_PAGES = [
        'panel_dashboard', 'panel_stats', 'panel_utm_list', 'panel_user_list',
        'panel_forum', 'panel_forum_topics', 'panel_forum_posts', 'panel_posts',
        'panel_post_categories', 'panel_nav_sections', 'panel_quiz', 'panel_shop',
        'panel_guestbook', 'panel_maintenance', 'panel_seasonal', 'panel_version',
        'panel_games', 'panel_games_mystery', 'panel_ephemerides',
        'panel_ephemerides_contributions', 'panel_memories',
        'panel_memory_comments', 'panel_memory_consoles',
    ]

    def _assert_pages_ok(self, names, user=None):
        client = Client(raise_request_exception=False)
        if user:
            client.force_login(user)
        for name in names:
            with self.subTest(page=name):
                response = client.get(reverse(name), follow=True)
                self.assertEqual(response.status_code, 200, f"{name} → {response.status_code}")

    def test_public_pages(self):
        self._assert_pages_ok(self.PUBLIC_PAGES)

    def test_public_pages_as_member(self):
        self._assert_pages_ok(self.PUBLIC_PAGES, self.member)

    def test_member_pages(self):
        self._assert_pages_ok(self.MEMBER_PAGES, self.member)

    def test_staff_pages(self):
        self._assert_pages_ok(self.STAFF_PAGES, self.staff)

    def test_forum_pages_with_content(self):
        client = Client(raise_request_exception=False)
        client.force_login(self.member)
        for url in [
            reverse('topic_list', args=[self.forum.id]),
            reverse('post_list', args=[self.forum.id, self.topic.id]),
            reverse('create_topic', args=[self.forum.id]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)

    def test_member_pages_require_login(self):
        for name in self.MEMBER_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertIn(response.status_code, (302, 403), name)

    def test_staff_pages_refused_to_members(self):
        self.client.force_login(self.member)
        for name in self.STAFF_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertIn(response.status_code, (302, 403), name)
