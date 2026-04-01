from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from posts.models import Post
from forum.models import Topic, Forum, Post as ForumPost
from users.models import UserLevel
from django.contrib import messages
from users.decorators import groups_required
from posts.forms import CreatePost, EditPost
from django.utils.text import slugify
from django.contrib.auth.decorators import login_required
from django.db.models import F
import os
import json

def view_post(request, slug):
    post = Post.objects.filter(slug=slug, active=True).first()
    if not post:
        from django.http import Http404
        raise Http404("Le post n'existe pas ou n'est pas actif.")

    subposts = None

    if post.parent:
        subposts = Post.objects.filter(post_parent=post.id)
    elif post.post_parent:
        subposts = Post.objects.filter(post_parent=post.post_parent.id)

    context = {
        'post': post,
        'subposts': subposts
    }

    return render(request, "posts/post.html", context)

@groups_required('Rédacteur', 'Admininistrateur', 'Super Admin')
def create_post(request, type):
    # Create a new post
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        active = request.POST.get('active') == 'on'
        image=request.FILES.get('image') if type == 'news' else None

        # Si c'est une news, on créer aussi un topic sur le forum news
        if type == 'news':
            topic = Topic.objects.create(
                title=title,
                forum=Forum.objects.get(name='Actus du site'),
                author=request.user
            )

            content_forum = f'<p><img src="/media/images/{image}"></p><p>{content}</p>'

            forum_post = ForumPost.objects.create(
                topic=topic,
                content=content_forum,
                author=request.user
            )

            UserLevel.objects.update(user=request.user, experience=F('experience') + 20)

            topic.save()
            forum_post.save()

        forum_link = f'forum/{topic.forum.id}/{topic.id}/'

        post = Post.objects.create(
            slug=slugify(title),
            title=title,
            content=content,
            type=type,
            image=image,
            author=request.user,
            active=active,
            forum_link=forum_link
        )

        post.save()



        messages.success(request, 'Post créer avec succès !')

        return redirect('home')

    context = {
        'type': type,
        'post_form': CreatePost(),
    }

    return render(request, "posts/create_post.html", context)

@login_required()
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)

    if request.method == 'POST':
        form = EditPost(request.POST, instance=post)
        if form.is_valid():
            post.title = form.cleaned_data['title']
            post.content = form.cleaned_data['content']
            post.active = False
            post.save()
            return redirect('contributions')
    else:
        form = CreatePost(initial={
            'title': post.title,
            'content': post.content,
        })

    return render(request, 'posts/edit_post.html', {'form': form, 'post': post})

@groups_required('Administrateur', 'Super Admin')
def prending_posts(request):
    posts = Post.objects.filter(active=False)

    return render(request, 'posts/pending_posts.html')


@login_required
@require_POST
def ai_assist(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        from mistralai.client import Mistral
    except ImportError:
        return JsonResponse({'error': 'Module mistralai non disponible'}, status=500)

    api_key = os.getenv('MISTRAL_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'Clé API Mistral non configurée'}, status=500)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    action = data.get('action')
    client = Mistral(api_key=api_key)

    type_labels = {
        'news': 'une actualité du monde rétro',
        'games': 'un article sur un jeu vidéo rétro',
        'movies': 'un article sur un film ou une série rétro',
        'music': 'un article sur la musique rétro',
        'tech': 'un article sur la technologie rétro',
    }

    if action == 'generate':
        title = data.get('title', '').strip()
        post_type = data.get('post_type', '')

        if not title:
            return JsonResponse({'error': 'Titre requis'}, status=400)

        type_label = type_labels.get(post_type, 'un article sur la culture rétro')

        system_prompt = (
            "Tu es un rédacteur passionné pour un site communautaire dédié à la culture rétro "
            "(jeux vidéo, films, séries, musique des années 70-90). "
            "Ton style est nostalgique, chaleureux, accessible et légèrement humoristique. Tu écris en français. "
            "Tu utilises du BBCode pour le formatage : [b]texte en gras[/b], [i]italique[/i], "
            "[t2]sous-titre[/t2], [t3]section[/t3]. "
            "Tu structures tes articles avec une introduction accrocheuse, un développement en sections "
            "et une conclusion qui invite à la discussion."
        )
        user_prompt = (
            f'Génère un article complet sur le sujet suivant : "{title}"\n'
            f"C'est {type_label}.\n"
            "L'article doit faire environ 400-600 mots, avec une introduction, "
            "2-3 sections développées et une conclusion. "
            "N'utilise pas le markdown"
            "Utilise le BBCode pour la mise en forme."
        )

        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        return JsonResponse({'content': response.choices[0].message.content})

    elif action == 'chat':
        messages_history = data.get('messages', [])
        current_content = data.get('current_content', '')

        system_prompt = (
            "Tu es un assistant éditorial pour un site communautaire rétro "
            "(jeux vidéo, films, séries des années 70-90). "
            "Tu aides à améliorer et affiner des articles. Tu écris en français. "
            "Tu utilises du BBCode pour le formatage si nécessaire : [b], [i], [t2], [t3], [quote], etc.\n\n"
            "Voici le contenu actuel de l'article en cours de rédaction :\n"
            "---\n"
            f"{current_content}\n"
            "---\n"
            "Tu peux reformuler, améliorer, suggérer des ajouts ou des corrections basées sur ce contenu."
        )

        mistral_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages_history:
            if msg.get('role') in ('user', 'assistant'):
                mistral_messages.append({"role": msg['role'], "content": msg['content']})

        response = client.chat.complete(
            model="mistral-small-latest",
            messages=mistral_messages
        )
        return JsonResponse({'reply': response.choices[0].message.content})

    return JsonResponse({'error': 'Action inconnue'}, status=400)