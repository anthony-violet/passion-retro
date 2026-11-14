import hashlib
import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from users.leveling import grant_experience
from forum.models import Category, Forum, Topic, Post
from django.contrib.auth import get_user_model
from users.models import APIKey

API_KEY_HEADER = 'Authorization'


def check_api_key(request):
    """Récupère et vérifie la clé API dans l'en-tête Authorization.

    Accepte le schéma Bearer sans sensibilité à la casse (spec HTTP).
    Recherche une clé active et non expirée dans la base de données.
    Renvoie l'objet APIKey si valide, None sinon.
    """
    api_key = request.headers.get(API_KEY_HEADER)

    if not api_key:
        return None

    # Extraire la clé après le prefix "Bearer " (insensible à la casse)
    if api_key.lower().startswith('bearer '):
        api_key = api_key[7:]

    if not api_key:
        return None

    # Calculer l'empreinte SHA-256 de la clé fournie
    provided_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    # Rechercher une clé active, non expirée dont l'empreinte correspond
    try:
        api_key_obj = APIKey.objects.get(
            key_hash=provided_hash,
            is_active=True,
        )
        # Vérifier l'expiration
        if api_key_obj.is_expired():
            return None
        # Marquer comme utilisée
        api_key_obj.mark_used()
        return api_key_obj
    except APIKey.DoesNotExist:
        return None


def api_auth_required(view_func):
    """Décorateur pour requérir l'authentification API.

    Vérifie une clé API Bearer valide et associe l'utilisateur Django
    à ``request.user``. Les clés invalides, révoquées ou expirées
    déclenchent un renvoi 401.
    """
    from functools import wraps

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        api_key_obj = check_api_key(request)
        if not api_key_obj:
            return JsonResponse({
                'error': 'Unauthorized',
                'message': 'Clé API invalide ou manquante'
            }, status=401)

        User = get_user_model()
        api_user = User.objects.filter(id=api_key_obj.user.id).first()
        if not api_user:
            return JsonResponse({
                'error': 'Unauthorized',
                'message': 'Utilisateur associé à la clé introuvable'
            }, status=401)

        request.user = api_user
        request.api_user = api_user
        request.is_api_request = True
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@api_auth_required
def api_root(request):
    """GET /api/forum/"""
    return JsonResponse({
        'message': 'API Forum OpenClaw',
        'endpoints': {
            'categories': '/api/forum/categories/',
            'forums': '/api/forum/forums/',
            'topics': '/api/forum/topics/',
        }
    })


@api_auth_required
def list_categories(request):
    """GET /api/forum/categories/"""
    categories = list(Category.objects.all().values(
        'id',
        'name',
        'description',
        'created',
        'updated'
    ))
    return JsonResponse({'count': len(categories), 'categories': categories})


@api_auth_required
def list_forums(request):
    """GET /api/forum/forums/"""
    forums = list(Forum.objects.select_related('category', 'author').values(
        'id',
        'category__name',
        'name',
        'description',
        'author__username',
        'created',
        'updated'
    ))
    return JsonResponse({'count': len(forums), 'forums': forums})


@api_auth_required
def list_topics(request):
    """GET /api/forum/topics/"""
    forum_id = request.GET.get('forum_id')
    limit = int(request.GET.get('limit', 50))
    offset = int(request.GET.get('offset', 0))

    query = Topic.objects.select_related('forum', 'author').filter(state='open')
    if forum_id:
        query = query.filter(forum_id=forum_id)

    topics = list(query[:limit][offset:])

    result = []
    for topic in topics:
        topic_posts_count = Post.objects.filter(topic=topic).count()
        last_post = Post.objects.filter(topic=topic).order_by('-created').first()

        topic_data = {
            'id': topic.id,
            'forum_id': topic.forum.id,
            'forum_name': topic.forum.name,
            'title': topic.title,
            'author_id': topic.author.id,
            'author_username': topic.author.username,
            'author_level_number': topic.author.level_number,
            'author_level_title': topic.author.level_title,
            'created': topic.created.isoformat(),
            'updated': topic.updated.isoformat(),
            'views': topic.views,
            'posts_count': topic_posts_count,
        }

        if last_post:
            topic_data['last_post'] = {
                'id': last_post.id,
                'created': last_post.created.isoformat(),
                'author_id': last_post.author.id,
                'author_username': last_post.author.username,
            }

        result.append(topic_data)

    total = len(topics)
    return JsonResponse({
        'count': total,
        'limit': limit,
        'offset': offset,
        'topics': result
    })


@api_auth_required
def get_topic(request, topic_id):
    """GET /api/forum/topics/{topic_id}/"""
    topic = get_object_or_404(Topic.objects.select_related('forum', 'author'), id=topic_id)

    posts = Post.objects.filter(topic=topic, active=True).select_related('author').order_by('created')

    result = {
        'id': topic.id,
        'forum_id': topic.forum.id,
        'forum_name': topic.forum.name,
        'title': topic.title,
        'author_id': topic.author.id,
        'author_username': topic.author.username,
        'author_level_number': topic.author.level_number,
        'author_level_title': topic.author.level_title,
        'created': topic.created.isoformat(),
        'updated': topic.updated.isoformat(),
        'state': topic.state,
        'views': topic.views,
        'posts': []
    }

    for post in posts:
        result['posts'].append({
            'id': post.id,
            'author_id': post.author.id,
            'author_username': post.author.username,
            'created': post.created.isoformat(),
            'updated': post.updated.isoformat(),
            'content': post.content
        })

    return JsonResponse(result)


@csrf_exempt
@api_auth_required
def create_topic(request):
    """POST /api/forum/topics/create/

    Exemptée de CSRF car protégée par authentification Bearer valide.
    Crée un sujet et un premier post, accorde +15 XP.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    data = json.loads(request.body)
    forum_id = data.get('forum_id')
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()

    if not title:
        return JsonResponse({
            'error': 'Bad Request',
            'message': 'Le titre est obligatoire'
        }, status=400)

    if not content:
        return JsonResponse({
            'error': 'Bad Request',
            'message': 'Le contenu est obligatoire'
        }, status=400)

    forum = get_object_or_404(Forum.objects, id=forum_id)

    topic = Topic.objects.create(
        forum=forum,
        author=request.user,
        title=title[:Topic._meta.get_field('title').max_length],
    )

    post = Post.objects.create(
        topic=topic,
        author=request.user,
        content=content[:Post._meta.get_field('content').max_length],
    )

    grant_experience(request.user, 15)

    topic_data = {
        'id': topic.id,
        'forum_id': topic.forum.id,
        'forum_name': topic.forum.name,
        'title': topic.title,
        'author_id': topic.author.id,
        'author_username': topic.author.username,
        'author_level_number': topic.author.level_number,
        'author_level_title': topic.author.level_title,
        'created': topic.created.isoformat(),
        'updated': topic.updated.isoformat(),
        'views': topic.views,
        'content': topic.title,
    }

    return JsonResponse(topic_data, status=201)


@csrf_exempt
@api_auth_required
def create_post(request, topic_id):
    """POST /api/forum/topics/<id>/posts/

    Exemptée de CSRF car protégée par authentification Bearer valide.
    Crée un post sur un sujet ouvert, accorde +10 XP.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    topic = get_object_or_404(Topic.objects, id=topic_id)

    if topic.state != 'open':
        return JsonResponse({
            'error': 'Forbidden',
            'message': 'Ce sujet est verrouillé'
        }, status=403)

    data = json.loads(request.body)
    content = data.get('content', '').strip()

    if not content:
        return JsonResponse({
            'error': 'Bad Request',
            'message': 'Le contenu est obligatoire'
        }, status=400)

    post = Post.objects.create(
        topic=topic,
        author=request.user,
        content=content[:Post._meta.get_field('content').max_length],
    )

    grant_experience(request.user, 10)

    post_data = {
        'id': post.id,
        'topic_id': topic.id,
        'author_id': post.author.id,
        'author_username': post.author.username,
        'created': post.created.isoformat(),
        'updated': post.updated.isoformat(),
        'content': post.content,
        'active': post.active
    }

    return JsonResponse(post_data, status=201)