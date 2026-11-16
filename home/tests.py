from django.test import TestCase
from django.urls import reverse
from posts.models import Post
from users.models import User

class HomeViewTest(TestCase):
    def setUp(self):
        # Créer un utilisateur pour les tests
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        # Créer une catégorie pour les posts
        from posts.models import Category
        self.category = Category.objects.create(name='Test Category')
        
        # Créer des posts pour les tests avec des slugs uniques
        import uuid
        
        self.edito = Post.objects.create(
            title='Édito test',
            content='Contenu édito',
            type='edito',
            active=True,
            author=self.user,
            slug=f'edito-test-{uuid.uuid4().hex[:8]}',
            category=self.category
        )
        
        self.news1 = Post.objects.create(
            title='News 1',
            content='Contenu news 1',
            type='news',
            active=True,
            author=self.user,
            slug=f'news-1-{uuid.uuid4().hex[:8]}',
            category=self.category
        )
        
        self.news2 = Post.objects.create(
            title='News 2',
            content='Contenu news 2',
            type='news',
            active=False,  # Inactive pour tester le filtrage
            author=self.user,
            slug=f'news-2-{uuid.uuid4().hex[:8]}',
            category=self.category
        )
    
    def test_home_page_status(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
    
    def test_home_page_uses_correct_template(self):
        response = self.client.get(reverse('home'))
        self.assertTemplateUsed(response, 'home.html')
    
    def test_home_page_shows_edito(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Édito test')
        self.assertContains(response, 'Contenu édito')
    
    def test_home_page_shows_active_news(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'News 1')
        self.assertNotContains(response, 'News 2')  # News inactive ne doit pas apparaître
    
    def test_home_page_shows_max_6_news(self):
        # Créer 5 news supplémentaires
        import uuid
        for i in range(5):
            Post.objects.create(
                title=f'News {i+3}',
                content=f'Contenu news {i+3}',
                type='news',
                active=True,
                author=self.user,
                slug=f'news-{i+3}-{uuid.uuid4().hex[:8]}',
                category=self.category
            )
        
        response = self.client.get(reverse('home'))
        # Compter le nombre de news affichées
        news_count = response.context['news'].count()
        self.assertEqual(news_count, 6)  # Doit être limité à 6

class Custom404Test(TestCase):
    def test_custom_404_page(self):
        # Tester une URL inexistante
        response = self.client.get('/url-inexistante/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'errors/404.html')


class SeoEndpointsTest(TestCase):
    def test_robots_txt(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('User-agent: *', content)
        self.assertIn('Sitemap:', content)

    def test_llms_txt(self):
        response = self.client.get('/llms.txt')
        self.assertEqual(response.status_code, 200)
        self.assertIn('# TestSite', response.content.decode())

    def test_sitemap_xml(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('<urlset', response.content.decode())

    def test_home_head_seo(self):
        response = self.client.get(reverse('home'))
        html = response.content.decode()
        self.assertIn('<h1 class="sr-only">', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn('application/ld+json', html)
        self.assertNotIn('name="keywords"', html)

    def test_private_page_is_noindex(self):
        response = self.client.get('/users/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'noindex, nofollow')


class DiscoverViewTest(TestCase):
    def setUp(self):
        import uuid

        self.user = User.objects.create_user(
            username='discoveruser',
            email='discover@test.com',
            password='testpass123'
        )
        from posts.models import Category
        self.category = Category.objects.create(name='Découverte')
        self.edito = Post.objects.create(
            title='Édito découverte',
            content='Contenu édito découverte',
            type='edito',
            active=True,
            author=self.user,
            slug=f'edito-decouverte-{uuid.uuid4().hex[:8]}',
            category=self.category
        )
        self.article = Post.objects.create(
            title='Article rétro',
            content='Un article consacré à la culture rétro.',
            type='news',
            active=True,
            author=self.user,
            slug=f'article-retro-{uuid.uuid4().hex[:8]}',
            category=self.category
        )
        self.inactive = Post.objects.create(
            title='Article inactif',
            content='Cet article ne doit pas apparaître.',
            type='news',
            active=False,
            author=self.user,
            slug=f'article-inactif-{uuid.uuid4().hex[:8]}',
            category=self.category
        )

    def test_discover_page_is_public(self):
        response = self.client.get(reverse('discover'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'discover.html')
        self.assertContains(response, "Et si on retrouvait le Web d'avant ?")
        self.assertContains(response, 'Le Petit Bac')
        self.assertContains(response, 'Les quiz')

    def test_discover_page_has_register_cta_for_anonymous(self):
        response = self.client.get(reverse('discover'))
        self.assertContains(response, reverse('register'))
        self.assertContains(response, 'Créer mon compte')

    def test_discover_page_has_profile_cta_for_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('discover'))
        self.assertContains(response, reverse('profile'))
        self.assertNotContains(response, 'Créer mon compte')

    def test_discover_page_lists_latest_active_non_edito_posts(self):
        import uuid
        for i in range(4):
            Post.objects.create(
                title=f'Article récent {i}',
                content='Contenu récent.',
                type='news',
                active=True,
                author=self.user,
                slug=f'article-recent-{i}-{uuid.uuid4().hex[:8]}',
                category=self.category
            )
        response = self.client.get(reverse('discover'))
        self.assertEqual(len(response.context['latest_posts']), 3)
        html = response.content.decode()
        self.assertEqual(html.count('Article récent'), 3)
        self.assertNotContains(response, 'Article inactif')

    def test_home_page_shows_discover_teaser(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Bienvenue sur')
        self.assertContains(response, "Retrouvons l'esprit du Web d'autrefois.")
        self.assertContains(response, reverse('discover'))
        self.assertContains(response, reverse('register'))

    def test_home_page_hides_register_cta_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('discover'))
        self.assertNotContains(response, reverse('register'))

    def test_discover_page_is_in_sitemap(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/decouvrir/', response.content.decode())


class NewsListViewTest(TestCase):
    def setUp(self):
        import datetime
        from django.utils import timezone
        from posts.models import Category

        self.user = User.objects.create_user(
            username='newsauthor', email='news@test.com', password='testpass123'
        )
        self.category = Category.objects.create(name='Actus')
        base = timezone.now()
        # 15 actus actives : « Actu 00 » est la plus ancienne, « Actu 14 » la plus récente.
        for i in range(15):
            post = Post.objects.create(
                title=f'Actu {i:02d}', content=f'Contenu actu {i}', type='news',
                active=True, author=self.user, slug=f'actu-{i:02d}', category=self.category,
            )
            Post.objects.filter(pk=post.pk).update(
                created=base - datetime.timedelta(days=15 - i)
            )
        Post.objects.create(
            title='Actu inactive', content='x', type='news', active=False,
            author=self.user, slug='actu-inactive', category=self.category,
        )
        Post.objects.create(
            title='Article pas actu', content='x', type='article', active=True,
            author=self.user, slug='article-pas-actu', category=self.category,
        )

    def test_news_list_status_and_template(self):
        response = self.client.get(reverse('news_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'news_list.html')
        self.assertEqual(reverse('news_list'), '/actus/')

    def test_news_list_shows_only_active_news(self):
        response = self.client.get(reverse('news_list'))
        self.assertEqual(response.context['paginator'].count, 15)
        self.assertNotContains(response, 'Actu inactive')
        self.assertNotContains(response, 'Article pas actu')

    def test_news_list_ordered_newest_first(self):
        response = self.client.get(reverse('news_list'))
        titles = [post.title for post in response.context['news']]
        self.assertEqual(titles[0], 'Actu 14')
        self.assertEqual(titles, sorted(titles, reverse=True))

    def test_news_list_pagination(self):
        page1 = self.client.get(reverse('news_list'))
        self.assertTrue(page1.context['is_paginated'])
        self.assertEqual(len(page1.context['news']), 12)
        self.assertContains(page1, '?page=2')

        page2 = self.client.get(reverse('news_list') + '?page=2')
        titles = [post.title for post in page2.context['news']]
        self.assertEqual(titles, ['Actu 02', 'Actu 01', 'Actu 00'])
        self.assertIn('page 2', page2.context['page_title'])

        out_of_range = self.client.get(reverse('news_list') + '?page=999')
        self.assertEqual(out_of_range.status_code, 200)
        self.assertEqual(out_of_range.context['page_obj'].number, 2)

    def test_news_list_empty(self):
        Post.objects.filter(type='news').delete()
        response = self.client.get(reverse('news_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aucune actu pour le moment.')
        self.assertFalse(response.context['is_paginated'])

    def test_home_links_to_news_list(self):
        response = self.client.get(reverse('home'))
        self.assertContains(
            response, f'<a href="{reverse("news_list")}">Toutes les actus »</a>', html=True
        )

    def test_menus_link_to_news_list(self):
        # Les middlewares de thème ne tournent pas en test : on rend directement
        # les deux menus (horizontal et vertical) choisis selon le thème.
        from django.contrib.auth.models import AnonymousUser
        from django.template.loader import render_to_string
        from django.test import RequestFactory

        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        for template in ('components/horizontal_menu.html', 'components/left_menu.html'):
            with self.subTest(template=template):
                html = render_to_string(template, request=request)
                self.assertInHTML(f'<a href="{reverse("news_list")}">Actus</a>', html)

    def test_news_list_is_in_sitemap(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/actus/</loc>', response.content.decode())
