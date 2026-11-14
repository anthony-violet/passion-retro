import hashlib
import json
from django.test import TestCase, Client
from django.contrib.auth.models import Group
from users.models import User, UserLevel, APIKey
from forum.models import Category, Forum, Topic, Post
from users.leveling import grant_experience


class ForumApiTests(TestCase):
    """Tests de l'API Forum - vérifie que les fonctionnalités API fonctionnent"""

    def setUp(self):
        """Préparation des fixtures pour les tests"""
        # Créer une catégorie
        self.category = Category.objects.create(
            name='Jeux Vidéo',
            description='Les jeux vidéo rétro'
        )
        
        # Créer un utilisateur admin pour les forums
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin',
            is_active=True
        )
        UserLevel.objects.create(user=self.admin_user, level=10, experience=1000)
        
        # Créer un forum
        self.forum = Forum.objects.create(
            category=self.category,
            author=self.admin_user,
            name='Jeux de plateau',
            description='Discutez de vos jeux de plateau préférés'
        )
        
        # Créer un utilisateur test
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            is_active=True
        )
        UserLevel.objects.create(user=self.test_user, level=1, experience=0)
        
        # Créer un sujet de test
        self.topic = Topic.objects.create(
            forum=self.forum,
            author=self.test_user,
            title='Premier sujet',
            state='open'
        )
        
        # Créer un premier post
        self.first_post = Post.objects.create(
            topic=self.topic,
            author=self.test_user,
            content='Bonjour à tous !'
        )
        
        # Utilisateur API Frce4 (existant dans OpenClaw)
        self.api_user = User.objects.get_or_create(
            username='Frce4',
            defaults={'email': 'api@nostalgeek.com', 'is_active': True}
        )[0]
        
        # Clé API de test (authentifie test_user)
        self.test_api_key = 'test_api_key_for_tests'
        # Créer l'objet APIKey en base pour que le nouveau système le reconnaisse
        APIKey.objects.create(
            user=self.test_user,
            name='Clé de test',
            key_hash=hashlib.sha256(self.test_api_key.encode('utf-8')).hexdigest(),
        )
        
        # Clé API pour Frce4 (authentifie l'utilisateur API)
        self.frce4_api_key = 'frce4_api_key_prod'
        APIKey.objects.create(
            user=self.api_user,
            name='Clé production Frce4',
            key_hash=hashlib.sha256(self.frce4_api_key.encode('utf-8')).hexdigest(),
        )
        
        self.client = Client()
        self.client.force_login(self.test_user)
    
    def make_api_request(self, method, path, data=None, api_key=None):
        """Utilitaire pour faire des requêtes API avec l'authentification"""
        key = api_key or self.test_api_key
        headers = {
            'Authorization': f'Bearer {key}'
        }
        
        if method == 'GET':
            response = self.client.get(path, headers=headers, **data if data else {})
        elif method == 'POST':
            response = self.client.post(path, data=json.dumps(data), content_type='application/json', headers=headers)
        elif method == 'PUT':
            response = self.client.put(path, data=json.dumps(data), content_type='application/json', headers=headers)
        elif method == 'DELETE':
            response = self.client.delete(path, headers=headers)
        
        return response
        """Utilitaire pour faire des requêtes API avec l'authentification"""
        headers = {
            'Authorization': f'Bearer {self.test_api_key}'
        }
        
        if method == 'GET':
            response = self.client.get(path, headers=headers, **data if data else {})
        elif method == 'POST':
            response = self.client.post(path, data=json.dumps(data), content_type='application/json', headers=headers)
        elif method == 'PUT':
            response = self.client.put(path, data=json.dumps(data), content_type='application/json', headers=headers)
        elif method == 'DELETE':
            response = self.client.delete(path, headers=headers)
        
        return response

    def test_list_categories(self):
        """Test lecture des catégories"""
        response = self.make_api_request('GET', '/api/forum/categories/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('count', data)
        self.assertIn('categories', data)
        self.assertGreaterEqual(data['count'], 1)
    
    def test_list_forums(self):
        """Test lecture des forums"""
        response = self.make_api_request('GET', '/api/forum/forums/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('count', data)
        self.assertIn('forums', data)
        self.assertGreaterEqual(data['count'], 1)
    
    def test_list_topics(self):
        """Test lecture des sujets"""
        response = self.make_api_request('GET', '/api/forum/topics/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('count', data)
        self.assertIn('topics', data)
        self.assertGreaterEqual(data['count'], 1)
        self.assertIn('limit', data)
        self.assertIn('offset', data)
    
    def test_get_topic(self):
        """Test lecture d'un sujet"""
        response = self.make_api_request('GET', f'/api/forum/topics/{self.topic.id}/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['id'], self.topic.id)
        self.assertEqual(data['title'], self.topic.title)
        self.assertEqual(data['forum_id'], self.topic.forum.id)
        self.assertEqual(data['state'], 'open')
        self.assertIn('posts', data)
        self.assertGreaterEqual(len(data['posts']), 1)
    
    def test_create_topic(self):
        """Test création d'un sujet"""
        data = {
            'forum_id': self.forum.id,
            'title': 'Nouveau sujet API',
            'content': 'Contenu du sujet créé via API'
        }
        
        response = self.make_api_request('POST', '/api/forum/topics/create/', data)
        
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['title'], 'Nouveau sujet API')
        self.assertIn('id', response_data)
        self.assertIn('created', response_data)
    
    def test_create_topic_with_empty_title(self):
        """Test création d'un sujet avec titre vide"""
        data = {
            'forum_id': self.forum.id,
            'title': '',
            'content': 'Contenu'
        }
        
        response = self.make_api_request('POST', '/api/forum/topics/create/', data)
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Bad Request')
    
    def test_create_topic_with_empty_content(self):
        """Test création d'un sujet avec contenu vide"""
        data = {
            'forum_id': self.forum.id,
            'title': 'Titre',
            'content': ''
        }
        
        response = self.make_api_request('POST', '/api/forum/topics/create/', data)
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Bad Request')
    
    def test_create_post(self):
        """Test création d'un post"""
        data = {
            'content': 'Réponse via API'
        }
        
        response = self.make_api_request('POST', f'/api/forum/topics/{self.topic.id}/posts/', data)
        
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['content'], 'Réponse via API')
        self.assertIn('id', response_data)
    
    def test_create_post_on_closed_topic(self):
        """Test création d'un post sur un sujet fermé"""
        self.topic.state = 'closed'
        self.topic.save()
        
        data = {
            'content': 'Réponse'
        }
        
        response = self.make_api_request('POST', f'/api/forum/topics/{self.topic.id}/posts/', data)
        
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Forbidden')
    
    def test_create_post_with_empty_content(self):
        """Test création d'un post avec contenu vide"""
        data = {
            'content': ''
        }
        
        response = self.make_api_request('POST', f'/api/forum/topics/{self.topic.id}/posts/', data)
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Bad Request')
    
    def test_pagination_topics(self):
        """Test pagination des sujets"""
        response = self.make_api_request('GET', '/api/forum/topics/?limit=2&offset=0')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['limit'], 2)
    
    def test_filter_topics_by_forum(self):
        """Test filtrage des sujets par forum"""
        response = self.make_api_request('GET', f'/api/forum/topics/?forum_id={self.forum.id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        for topic in data['topics']:
            self.assertEqual(topic['forum_id'], self.forum.id)
    
    # === Tests d'authentification API ===
    
    def test_api_key_valid(self):
        """Test qu'une requête avec une clé valide retourne HTTP 200"""
        response = self.make_api_request('GET', '/api/forum/categories/')
        self.assertEqual(response.status_code, 200)
    
    def test_api_key_missing(self):
        """Test qu'une requête sans clé retourne HTTP 401"""
        response = self.client.get('/api/forum/categories/')
        self.assertEqual(response.status_code, 401)
    
    def test_api_key_incorrect(self):
        """Test qu'une requête avec une clé incorrecte retourne HTTP 401"""
        response = self.client.get('/api/forum/categories/', HTTP_AUTHORIZATION='Bearer wrong_key')
        self.assertEqual(response.status_code, 401)
    
    def test_malformed_bearer(self):
        """Test qu'un header Bearer mal formé retourne HTTP 401"""
        response = self.client.get('/api/forum/categories/', HTTP_AUTHORIZATION='Bearer')
        self.assertEqual(response.status_code, 401)
    
    def test_api_user_is_Frce4(self):
        """Test que l'utilisateur authentifié est bien Frce4"""
        response = self.make_api_request('GET', '/api/forum/categories/', api_key=self.frce4_api_key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.api_user.username, 'Frce4')
    
    def test_endpoints_protected(self):
        """Test que les endpoints catégories, forums et sujets restent protégés"""
        # catégories
        response = self.make_api_request('GET', '/api/forum/categories/')
        self.assertEqual(response.status_code, 200)
        # forums
        response = self.make_api_request('GET', '/api/forum/forums/')
        self.assertEqual(response.status_code, 200)
        # sujets
        response = self.make_api_request('GET', '/api/forum/topics/')
        self.assertEqual(response.status_code, 200)