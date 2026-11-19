"""Les articles proposés par des membres ne peuvent pas injecter de HTML."""

from django.test import TestCase
from django.urls import reverse

from posts.models import Category, Post
from users.models import User

SCRIPT = '<script>alert("vol")</script>'


class ArticleHtmlEscapingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Jeux')
        cls.member = User.objects.create_user(username='membre', password='p')
        cls.staff = User.objects.create_user(username='redac', password='p', is_staff=True)

    def article(self, author, content, slug, type='news', active=True):
        return Post.objects.create(
            title=f'Article {slug}', slug=slug, content=content, type=type,
            author=author, category=self.category, active=active,
        )

    def test_member_article_script_escaped(self):
        for type_ in ('news', 'tuto'):
            with self.subTest(type=type_):
                post = self.article(self.member, f'Intro {SCRIPT} [b]gras[/b]', f'membre-{type_}', type=type_)
                response = self.client.get(reverse('view_post', args=[post.slug]))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, SCRIPT)
                self.assertContains(response, '<strong>gras</strong>')

    def test_member_article_escaped_for_staff_reviewer(self):
        # Article en attente : le staff l'ouvre pour le relire.
        post = self.article(self.member, SCRIPT, 'en-attente', active=False)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('view_post', args=[post.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, SCRIPT)

    def test_member_article_escaped_on_discover(self):
        self.article(self.member, SCRIPT, 'decouvrir')
        response = self.client.get(reverse('discover'))
        self.assertContains(response, 'Article decouvrir')
        self.assertNotContains(response, SCRIPT)

    def test_staff_article_html_kept(self):
        post = self.article(self.staff, '<center>Annonce officielle</center>', 'staff')
        response = self.client.get(reverse('view_post', args=[post.slug]))
        self.assertContains(response, '<center>Annonce officielle</center>')
        self.assertContains(self.client.get(reverse('discover')), '<center>Annonce officielle</center>')

    def test_preview_escapes_for_member(self):
        self.client.force_login(self.member)
        html = self.client.post(reverse('preview_content'), {'content': SCRIPT}).json()['html']
        self.assertNotIn('<script>', html)

    def test_preview_keeps_html_for_staff(self):
        self.client.force_login(self.staff)
        html = self.client.post(reverse('preview_content'), {'content': '<center>x</center>'}).json()['html']
        self.assertIn('<center>x</center>', html)
