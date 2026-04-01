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
