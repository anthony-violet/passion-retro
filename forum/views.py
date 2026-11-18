from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .models import Category, Forum, Topic, Post, TopicRead, TopicSubscription
from .forms import CreateTopic, CreatePost, EditPost
from .notifications import notify_topic_subscribers, update_subscription
from django.db.models import Max, F
from users.decorators import groups_required
from users.leveling import GOLD_BIG_ACTION, GOLD_SMALL_ACTION, grant_experience
from passion_retro.seo import absolute_url, breadcrumb_jsonld, discussion_jsonld, plain_text
from posts.models import Post as Article

MODERATOR_GROUPS = ('Modérateur', 'Admininistrateur', 'Super Admin')


def _is_moderator(user):
    return bool(
        user.is_authenticated
        and user.groups.filter(name__in=MODERATOR_GROUPS).exists()
    )

def forum_home(request):
    categories = Category.objects.all()
    forums = Forum.objects.all()

    last_posts = {}
    count_topics = {}
    unread_topics = {}

    for forum in forums:
        # Dernier post du forum avec une seule requête
        last_post = Post.objects.select_related(
            'topic', 
            'author',
            'topic__forum'
        ).filter(
            topic__forum=forum
        ).order_by('-created').first()
        
        last_posts[forum.id] = last_post
        
        # Nombre de topics (pas de changement)
        count_topic = Topic.objects.filter(forum=forum).count()
        count_topics[forum.id] = count_topic

        # Vérification des topics non lus
        if request.user.is_authenticated:
            # Récupérer le dernier post de chaque topic du forum en une seule requête
            latest_posts_per_topic = list(
                Post.objects.filter(
                    topic__forum=forum
                ).values('topic_id').annotate(
                    last_post_date=Max('created')
                )
            )

            # Récupérer les dernières lectures de l'utilisateur pour tous les topics du forum
            topic_reads = TopicRead.objects.filter(
                user=request.user,
                topic__forum=forum
            ).values_list('topic_id', 'last_read')

            # Dernière lecture de l'utilisateur dans ce forum
            forum_last_read = max(
                (last_read for _, last_read in topic_reads),
                default=None
            )

            if not latest_posts_per_topic:
                unread_topics[forum.id] = False
            elif forum_last_read is None:
                # Aucune lecture dans ce forum : tout est non lu
                unread_topics[forum.id] = True
            else:
                # Un forum est non lu si un post est plus récent que la dernière
                # lecture de l'utilisateur dans ce forum. On n'exige pas d'avoir
                # ouvert tous les anciens topics.
                unread_topics[forum.id] = any(
                    post_info['last_post_date'] > forum_last_read
                    for post_info in latest_posts_per_topic
                )
        else:
            unread_topics[forum.id] = False
    
    context = {
        'categories': categories,
        'forums': forums,
        'last_posts': last_posts,
        'count_topics': count_topics,
        'unread_topics': unread_topics,
        'page_title': f"Forum - {settings.SITE_NAME}",
        'page_heading': "Forum",
        'page_description': (
            f"Participez aux discussions de la communauté {settings.SITE_NAME} : "
            "jeux vidéo, films, séries et culture rétro."
        ),
    }

    return render(request, "components/forum_home.html", context)

def topic_list(request, forum_id):
    forum = get_object_or_404(Forum, id=forum_id)
    topics = Topic.objects.filter(forum=forum)
    if not _is_moderator(request.user):
        topics = topics.filter(active=True)
    topics = topics.select_related(
        'author'
    ).annotate(
        last_post_date=Max('posts__created')
    ).order_by('-last_post_date')
    paginator = Paginator(topics, 20)

    page_number = request.GET.get('page')
    topics = paginator.get_page(page_number)

    count_posts = {}
    last_posts = {}
    page_numbers = {}
    unread_topics = {}

    for topic in topics:
        count_post = Post.objects.filter(topic=topic).count()
        count_posts[topic.id] = count_post

        last_post = Post.objects.select_related(
            'author'
        ).filter(topic=topic).order_by('-created').first()
        last_posts[topic.id] = last_post

        if request.user.is_authenticated:
            # Récupérer le dernier post du topic
            latest_post = Post.objects.filter(topic=topic).aggregate(last_post_date=Max('created'))['last_post_date']
            
            # Récupérer la dernière lecture de l'utilisateur pour ce topic
            topic_read = TopicRead.objects.filter(user=request.user, topic=topic).first()
            
            # Un topic est non lu si le dernier post est plus récent que la dernière lecture
            if topic_read:
                unread_topics[topic.id] = latest_post > topic_read.last_read
            else:
                unread_topics[topic.id] = True
        else:
            unread_topics[topic.id] = False

        if last_post:
            # Position du dernier message (nombre de messages jusqu'à ce message)
            post_position = Post.objects.filter(
                topic=topic,
                created__lte=last_post.created
            ).count()
            
            # Calcul du numéro de page (20 messages par page comme dans topic_detail)
            page_number = (post_position + 19) // 20  # équivalent à ceil(post_position/20)
            page_numbers[topic.id] = page_number

    context = {
        'forum': forum,
        'topics': topics,
        'count_posts': count_posts,
        'last_posts': last_posts,
        'page_numbers': page_numbers,
        'unread_topics': unread_topics,
        'is_paginated': topics.has_other_pages(),
        'page_obj': topics,
        'paginator': paginator,
        'page_title': f"{forum.name} - Forum - {settings.SITE_NAME}",
        'page_heading': forum.name,
        'page_description': (
            forum.description
            or f"Les sujets du forum {forum.name} sur {settings.SITE_NAME}."
        ),
        'seo_page_jsonld': breadcrumb_jsonld([
            ("Forum", reverse("forum_home")),
            (forum.name, reverse("topic_list", args=[forum.id])),
        ]),
    }

    return render(request, "forum/topic_list.html", context)

@login_required
def create_topic(request, forum_id):
    if not request.user.is_active:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à créer un sujet.")

    forum = get_object_or_404(Forum, id=forum_id)

    if request.method == 'POST':
        topic_form = request.POST
        # On créer le topic via le model Topic
        topic = Topic(
            forum=forum,
            author=request.user,
            title=topic_form['title'],
        )

        # Puis le premier post du topic
        post = Post(
            topic=topic,
            author=request.user,
            content=topic_form['content'],
        )

        topic.save()
        post.save()
        update_subscription(
            request.user,
            topic,
            request.POST.get('subscribe') == 'on',
        )
        notify_topic_subscribers(post)
        messages.success(request, 'Topic créer avec succès.')
        grant_experience(request.user, 15, gold=GOLD_BIG_ACTION)
        # on renvoie l'utilisateur sur la page du topic contenu l'id du forum et du topic créer
        return redirect('post_list', forum_id=forum_id, topic_id=topic.id)
    
    topic_form = CreateTopic()
    context = {
        'forum': forum,
        'topic_form': topic_form,
    }
    return render(request, "forum/create_topic.html", context)

def topic_detail(request, topic_id, forum_id):
    topic = get_object_or_404(
        Topic.objects.select_related('author', 'forum').prefetch_related(
            'author__levels'
        ),
        id=topic_id,
    )
    if not topic.active and not _is_moderator(request.user):
        raise Http404("Ce sujet n'existe pas ou a été désactivé.")

    # Une seule URL par sujet : /forum/<mauvais_forum>/<topic>/ → 301
    if topic.forum_id != forum_id:
        target = reverse('post_list', args=[topic.forum_id, topic.id])
        if request.META.get('QUERY_STRING'):
            target = f"{target}?{request.META['QUERY_STRING']}"
        return redirect(target, permanent=True)

    if request.method == 'GET':
        Topic.objects.filter(pk=topic_id).update(views=F('views') + 1)

    subscription = None
    if request.user.is_authenticated:
        subscription = TopicSubscription.objects.filter(
            user=request.user,
            topic=topic,
        ).first()
    subscribe_initial = subscription.active if subscription else True
    post_form = CreatePost(initial={'subscribe': subscribe_initial})

    if request.method == 'POST':
        if not request.user.is_active or not request.user.is_authenticated:
            return HttpResponseForbidden("Vous n'êtes pas autorisé à poster un message.")

        post_form = CreatePost(request.POST)
        if post_form.is_valid():
            post = Post(
                topic=topic,
                author=request.user,
                content=post_form.cleaned_data['content'],
            )
            post.save()
            subscription = update_subscription(
                request.user,
                topic,
                post_form.cleaned_data.get('subscribe', False),
            )
            notify_topic_subscribers(post)
            grant_experience(request.user, 10, gold=GOLD_SMALL_ACTION)
            messages.success(request, 'Message posté avec succès.')
            post_form = CreatePost(
                initial={'subscribe': subscription.active},
            )

    posts = Post.objects.filter(
        topic=topic, active=True
    ).select_related('author').prefetch_related('author__levels').order_by(
        'created'
    )
    paginator = Paginator(posts, 20)

    page_number = request.GET.get('page')
    posts = paginator.get_page(page_number)

    # Marquer comme lu si l'utilisateur est connecté
    if request.user.is_authenticated:
        TopicRead.objects.update_or_create(
            user=request.user,
            topic=topic,
            defaults={'last_read': timezone.now()}
        )

    # On compte le nombre de posts de l'auteur
    count_posts = {}
    for post in posts:
        count_post = Post.objects.filter(author=post.author).count()
        count_posts[post.author.id] = count_post

    context = {
        'topic': topic,
        'posts': posts,
        'count_posts': count_posts,
        'post_form': post_form,
        'is_paginated': posts.has_other_pages(),
        'page_obj': posts,
        'paginator': paginator,
        'page_title': f"{topic.title} - Forum - {settings.SITE_NAME}",
        'page_heading': topic.title,
        'page_description': plain_text(posts[0].content, 160) if posts else (
            f"Sujet « {topic.title} » du forum {topic.forum.name}."
        ),
        'seo_og_type': 'article',
        'seo_page_jsonld': discussion_jsonld(
            request,
            topic,
            posts.paginator.count,
            [
                ("Forum", reverse("forum_home")),
                (topic.forum.name, reverse("topic_list", args=[topic.forum.id])),
                (topic.title, request.path),
            ],
        ),
    }

    # Les news sont recopiées dans un sujet du forum : on désigne l'article
    # comme version canonique pour éviter le contenu dupliqué.
    article = Article.objects.filter(
        active=True,
        # Même règle que le sitemap : on ne compare que l'id du sujet.
        forum_link__regex=rf"^/?forum/\d+/{topic.id}/?$",
    ).only('slug').first()
    if article:
        context['seo_canonical'] = absolute_url(
            request, reverse('view_post', args=[article.slug])
        )

    return render(request, "forum/topic_detail.html", context)

@require_http_methods(['GET', 'POST'])
def unsubscribe_topic(request, token):
    subscription = get_object_or_404(
        TopicSubscription.objects.select_related('topic__forum', 'user'),
        token=token,
    )
    if request.method == 'POST' and subscription.active:
        subscription.active = False
        subscription.save(update_fields=['active', 'updated'])

    context = {
        'subscription': subscription,
        'done': request.method == 'POST',
        'page_title': f"Désabonnement - {settings.SITE_NAME}",
        'page_heading': "Désabonnement",
    }
    return render(request, 'forum/unsubscribe.html', context)

@groups_required('Modérateur', 'Admininistrateur', 'Super Admin')
def lock_topic(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    topic.state = 'closed'
    topic.save()
    messages.success(request, 'Sujet verrouillé avec succès.')
    return redirect('post_list', forum_id=topic.forum.id, topic_id=topic_id)

@groups_required('Modérateur', 'Admininistrateur', 'Super Admin')
def unlock_topic(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    topic.state = 'open'
    topic.save()
    messages.success(request, 'Sujet déverrouillé avec succès.')
    return redirect('post_list', forum_id=topic.forum.id, topic_id=topic_id)

@groups_required('Modérateur', 'Admininistrateur', 'Super Admin')
def deactivate_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.active = False
    post.save()
    messages.success(request, 'Message désactivé avec succès.')
    return redirect('post_list', forum_id=post.topic.forum.id, topic_id=post.topic.id)

@groups_required('Modérateur', 'Admininistrateur', 'Super Admin')
def activate_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.active = True
    post.save()
    messages.success(request, 'Message activé avec succès.')
    return redirect('post_list', forum_id=post.topic.forum.id, topic_id=post.topic.id)

@groups_required('Modérateur', 'Admininistrateur', 'Super Admin')
def deactivate_topic(request, topic_id, forum_id=None):
    topic = get_object_or_404(Topic, id=topic_id)
    topic.active = False
    topic.save(update_fields=['active'])
    messages.success(request, 'Sujet désactivé avec succès.')
    return redirect('topic_list', forum_id=topic.forum.id)

@groups_required('Modérateur', 'Admininistrateur', 'Super Admin')
def activate_topic(request, topic_id, forum_id=None):
    topic = get_object_or_404(Topic, id=topic_id)
    topic.active = True
    topic.save(update_fields=['active'])
    messages.success(request, 'Sujet activé avec succès.')
    return redirect('topic_list', forum_id=topic.forum.id)

@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    # Vérifier si l'utilisateur a le droit d'éditer
    if not (request.user == post.author or request.user.groups.filter(name__in=['Administrateur', 'Super Admin']).exists()):
        return HttpResponseForbidden("Vous n'êtes pas autorisé à éditer ce message.")
    
    if request.method == 'POST':
        form = EditPost(request.POST)
        if form.is_valid():
            post.content = form.cleaned_data['content']
            post.updated = timezone.now()
            post.save()
            messages.success(request, 'Message modifié avec succès.')
            return redirect('post_list', forum_id=post.topic.forum.id, topic_id=post.topic.id)
    else:
        form = EditPost(initial={'content': post.content})
    
    context = {
        'form': form,
        'post': post
    }
    return render(request, "forum/edit_post.html", context)