from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from posts.models import Post, Category, NavSection
from forum.models import Topic, Forum, Post as ForumPost
from users.leveling import grant_experience
from django.contrib import messages
from users.decorators import groups_required
from posts.forms import CreatePost, EditPost, ContributionForm, NewsFieldsForm, parse_chapters
from posts.utils import unique_slug
from posts.news import (
    XP_FIRST_REACTION_BONUS, XP_REACTION, latest_reactions, news_queryset,
    publish_news, react_to_news, topic_url,
)
from django.urls import reverse
from django.db import transaction
from django.template.loader import render_to_string
from django.http import Http404
from django.utils.text import slugify
from django.contrib.auth.decorators import login_required
from passion_retro.seo import article_jsonld, media_og_image, plain_text
import os
import json

def _can_preview(user, post):
    if not user.is_authenticated:
        return False
    if post.author_id == user.id:
        return True
    # Un brouillon reste privé tant que l'auteur ne l'a pas envoyé.
    return user.is_staff and not post.draft


def view_post(request, slug):
    post = Post.objects.select_related('author', 'category', 'post_parent').filter(slug=slug).first()
    if not post or (not post.active and not _can_preview(request.user, post)):
        raise Http404("Le post n'existe pas ou n'est pas actif.")

    is_preview = not post.active
    can_review = request.user.is_authenticated and request.user.is_staff

    subposts = None
    if post.parent:
        subposts = Post.objects.filter(post_parent=post.id)
    elif post.post_parent:
        subposts = Post.objects.filter(post_parent=post.post_parent)
    dossier = post.post_parent or post
    if subposts is not None:
        subposts = subposts.order_by('id')
        # Les chapitres en attente ne sont visibles que de l'équipe et de l'auteur.
        if not _can_preview(request.user, dossier):
            subposts = subposts.filter(active=True)
        subposts = list(subposts)

    # Navigation précédent / suivant dans le dossier : introduction puis chapitres.
    previous_post = next_post = None
    if subposts:
        sequence = list(subposts)
        if dossier.active or _can_preview(request.user, dossier):
            sequence.insert(0, dossier)
        ids = [p.pk for p in sequence]
        if post.pk in ids:
            index = ids.index(post.pk)
            previous_post = sequence[index - 1] if index > 0 else None
            next_post = sequence[index + 1] if index + 1 < len(sequence) else None

    breadcrumbs = []
    if post.post_parent:
        breadcrumbs.append((post.post_parent.title, f"/posts/{post.post_parent.slug}/"))
    breadcrumbs.append((post.title, request.path))

    context = {
        'post': post,
        'subposts': subposts,
        'is_preview': is_preview,
        'previous_post': previous_post,
        'next_post': next_post,
        'show_review_bar': _can_preview(request.user, post) and (
            is_preview or (subposts is not None and any(not p.active for p in subposts))
        ),
        'can_review': can_review,
        'dossier': dossier,
        'pending_chapters': [
            p for p in (subposts or [])
            if not p.active and not p.draft and p.post_parent_id == dossier.id
            and (dossier.rejected or not p.rejected)
        ],
        'nav_section': dossier.nav_section,
        'review_categories': Category.objects.order_by('name') if can_review else None,
        'page_title': f"{post.title} - {settings.SITE_NAME}",
        'page_heading': post.title,
        'page_description': plain_text(post.content, 160),
        'seo_og_type': 'article',
        'seo_og_image': media_og_image(request, post.image),
        'seo_page_jsonld': article_jsonld(request, post, breadcrumbs),
    }
    if is_preview:
        context['seo_noindex'] = True

    if post.type == 'news' and not post.post_parent_id:
        if post.active and not post.topic_id:
            # Actu publiée avant l'arrivée des discussions : on crée son sujet maintenant.
            publish_news(post)
        context.update(_news_context(request, post))
        return render(request, "posts/news_detail.html", context)

    return render(request, "posts/post.html", context)


def _news_context(request, post):
    """Données propres à la page d'une actu : discussion forum et actus voisines."""
    from forum.models import TopicSubscription

    news = news_queryset()
    annotated = news.filter(pk=post.pk).first()
    pub_date = annotated.pub_date if annotated else post.publication_date
    reactions_count = annotated.reactions if annotated else 0
    last_activity = annotated.last_activity if annotated else None

    previous_news = news.filter(pub_date__lt=pub_date).first() if post.active else None
    next_news = news.filter(pub_date__gt=pub_date).order_by('pub_date', 'pk').first() if post.active else None
    related = list(news.exclude(pk=post.pk).filter(category_id=post.category_id)[:3])
    if len(related) < 3:
        related += list(news.exclude(pk__in=[post.pk, *[r.pk for r in related]])[:3 - len(related)])

    subscribe_initial = True
    first_reaction = True
    if request.user.is_authenticated and post.topic_id:
        subscription = TopicSubscription.objects.filter(user=request.user, topic_id=post.topic_id).first()
        if subscription:
            subscribe_initial = subscription.active
        first_reaction = not ForumPost.objects.filter(topic_id=post.topic_id, author=request.user).exists()

    return {
        'news_pub_date': pub_date,
        'reactions': latest_reactions(post, 3),
        'reactions_count': reactions_count,
        'last_activity': last_activity,
        'topic_url': topic_url(post.topic) if post.topic_id else None,
        'topic_locked': bool(post.topic_id and post.topic.state == 'closed'),
        'previous_news': previous_news,
        'next_news': next_news,
        'related_news': related,
        'subscribe_initial': subscribe_initial,
        'first_reaction': first_reaction,
        'xp_reaction': XP_REACTION + (XP_FIRST_REACTION_BONUS if first_reaction else 0),
        'xp_bonus': XP_FIRST_REACTION_BONUS,
    }


@login_required
@require_POST
def news_react(request, slug):
    """Réaction rapide depuis la page d'une actu : publiée dans le sujet du forum."""
    post = get_object_or_404(Post.objects.select_related('topic'), slug=slug, type='news', active=True)
    target = reverse('view_post', args=[post.slug]) + '#discussion'
    if not post.topic_id or not request.user.is_active:
        messages.error(request, "La discussion n'est pas disponible pour cette actu.")
        return redirect(target)
    if post.topic.state == 'closed' or not post.topic.active:
        messages.error(request, 'Cette discussion est fermée.')
        return redirect(target)
    content = request.POST.get('content', '').strip()
    if not content:
        messages.error(request, 'Écris un message avant de publier ta réaction.')
        return redirect(target)
    _, xp = react_to_news(post, request.user, content, request.POST.get('subscribe') == 'on')
    messages.success(request, f'Réaction publiée sur le forum. +{xp} XP !')
    return redirect(target)

@groups_required('Rédacteur', 'Admininistrateur', 'Super Admin')
def create_post(request, type):
    # Create a new post
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        active = request.POST.get('active') == 'on'
        image=request.FILES.get('image') if type == 'news' else None
        news_form = NewsFieldsForm(request.POST) if type == 'news' else None
        if news_form is not None and not news_form.is_valid():
            messages.error(request, "Certains champs de l'actu sont invalides.")
            return render(request, "posts/create_post.html", {
                'type': type, 'post_form': CreatePost(request.POST), 'news_form': news_form,
            })
        news_fields = news_form.cleaned_data if news_form is not None else {}

        post = Post.objects.create(
            slug=unique_slug(title),
            category=_news_category() or Category.objects.first(),
            title=title,
            content=content,
            type=type,
            image=image,
            author=request.user,
            active=active,
            **news_fields,
        )
        # Le sujet du forum n'est créé qu'une fois l'actu en ligne.
        publish_news(post)

        messages.success(request, 'Post créer avec succès !')

        return redirect('home')

    context = {
        'type': type,
        'post_form': CreatePost(),
        'news_form': NewsFieldsForm() if type == 'news' else None,
    }

    return render(request, "posts/create_post.html", context)

CONTRIBUTION_TYPES = {
    'article': 'Écrire un article',
    'games': 'Écrire un article Jeux vidéo',
    'movies': 'Écrire un article Films & Séries',
    'music': 'Écrire un article Musique',
    'musics': 'Écrire un article Musique',
    'tech': 'Écrire un article Technologie',
    'news': 'Proposer une actualité',
}


def _news_category():
    return Category.objects.filter(name__iexact='Actualités').first()


def contribution_form(request, type, post=None):
    """Création ou modification d'une contribution (article seul ou dossier)."""
    if type == 'musics':
        type = 'music'
    is_news = type == 'news'
    with_category = not is_news and (post is None or post.parent)
    existing_children = list(post.child_posts.order_by('id')) if post else []

    # Un brouillon n'est possible que tant que la contribution n'a jamais été envoyée.
    can_save_draft = post is None or post.draft

    if request.method == 'POST':
        is_draft = request.POST.get('action') == 'draft' and can_save_draft
        form = ContributionForm(request.POST, with_category=with_category)
        if is_draft:
            # Un brouillon peut être incomplet : seul le titre est obligatoire.
            form.fields['content'].required = False
            if 'category' in form.fields:
                form.fields['category'].required = False
        is_dossier = bool(existing_children) or (request.POST.get('format') == 'dossier' and not is_news)
        chapters, chapter_errors = parse_chapters(request.POST) if is_dossier else ([], [])
        if is_draft:
            chapter_errors = []
            for chapter in chapters:
                chapter.pop('error', None)
                if not chapter['title']:
                    chapter['title'] = f"Chapitre {chapter['number']} (sans titre)"
                chapter['title'] = chapter['title'][:150]
        elif is_dossier and not chapters:
            form.add_error(None, "Un dossier doit contenir au moins un chapitre. Ajoute un chapitre ou choisis « Article seul ».")

        if form.is_valid() and not chapter_errors and not form.non_field_errors():
            data = form.cleaned_data
            with transaction.atomic():
                if is_news:
                    category = _news_category()
                elif with_category and data.get('category'):
                    category = Category.objects.get(pk=data['category'])
                elif post is not None:
                    category = post.category
                else:
                    category = None

                if post is None:
                    main = Post(
                        type=type, author=request.user, contribution=True, active=False,
                        category=category or Category.objects.order_by('pk').first(),
                    )
                    created = True
                else:
                    main = post
                    created = False
                first_submission = not is_draft and (created or main.draft)
                changed = (
                    created or first_submission or main.draft != is_draft
                    or (main.rejected and not is_draft)
                    or main.title != data['title'] or main.content != data['content']
                    or (category is not None and with_category and main.category_id != category.id)
                )
                if changed:
                    if main.title != data['title'] or not main.slug or main.slug == 'default-slug':
                        main.slug = unique_slug(data['title'], exclude_pk=main.pk)
                    main.title = data['title']
                    main.content = data['content']
                    if category is not None and (with_category or created):
                        main.category = category
                    main.active = False
                    main.draft = is_draft
                    main.rejected = False
                    main.rejection_reason = ''
                    main.contribution = True
                    main.save()

                kept_ids = set()
                children_by_id = {str(child.id): child for child in existing_children}
                for chapter in chapters:
                    child = children_by_id.get(chapter['id'])
                    if child:
                        kept_ids.add(child.id)
                        # Un chapitre refusé repart en relecture avec le dossier, même inchangé.
                        if (child.title == chapter['title'] and child.content == chapter['content']
                                and child.draft == is_draft and not child.rejected):
                            continue
                        if child.title != chapter['title']:
                            child.slug = unique_slug(chapter['title'], exclude_pk=child.pk)
                        child.title = chapter['title']
                        child.content = chapter['content']
                        child.active = False
                        child.draft = is_draft
                        child.rejected = False
                        child.rejection_reason = ''
                        child.contribution = True
                        child.save()
                    else:
                        Post.objects.create(
                            title=chapter['title'], slug=unique_slug(chapter['title']),
                            content=chapter['content'], type=type, author=request.user,
                            contribution=True, active=False, draft=is_draft, post_parent=main,
                            category=main.category,
                        )
                # Les chapitres retirés qui n'étaient pas encore publiés sont supprimés.
                if post is not None and post.parent:
                    for child in existing_children:
                        if child.id not in kept_ids and not child.active:
                            child.delete()

                # L'expérience n'est gagnée qu'au premier envoi, pas pour un brouillon.
                if first_submission:
                    grant_experience(request.user, 10 + 5 * len(chapters))

            if is_draft:
                messages.success(request, "Brouillon enregistré. Il n'est visible que par toi : reviens le terminer quand tu veux.")
                return redirect('edit_post', post_id=main.id)
            if first_submission:
                messages.success(request, "Merci ! Ta contribution a été envoyée à l'équipe. Voici l'aperçu tel qu'il apparaîtra sur le site.")
            else:
                messages.success(request, "Modifications enregistrées. Ta contribution repasse en relecture.")
            return redirect('view_post', slug=main.slug)
    else:
        initial = {}
        if post is not None:
            initial = {'title': post.title, 'content': post.content, 'category': post.category_id}
        elif request.GET.get('rubrique', '').isdigit():
            initial['category'] = int(request.GET['rubrique'])
        form = ContributionForm(initial=initial, with_category=with_category)
        is_dossier = bool(existing_children)
        chapters = [
            {'id': str(child.id), 'title': child.title, 'content': child.content,
             'active': child.active, 'number': index}
            for index, child in enumerate(existing_children, start=1)
        ]

    published_ids = {str(child.id) for child in existing_children if child.active}
    for chapter in chapters:
        chapter['active'] = chapter.get('id') in published_ids

    context = {
        'type': type,
        'heading': ('Modifier ma contribution' if post else CONTRIBUTION_TYPES.get(type, 'Écrire un article')),
        'form': form,
        'post': post,
        'is_news': is_news,
        'is_dossier': is_dossier,
        'chapters': chapters,
        'can_be_dossier': not is_news and (post is None or post.parent),
        'nav_categories': {cat.id: label for cat, label in form.category_choices},
        'draft_key': f'contrib-draft-{post.id if post else type}',
        'can_save_draft': can_save_draft,
    }
    return render(request, 'posts/contribution_form.html', context)


@login_required()
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    # Un chapitre se modifie depuis son dossier.
    if post.post_parent_id and post.post_parent.author_id == request.user.id:
        return redirect('edit_post', post_id=post.post_parent_id)
    return contribution_form(request, post.type, post=post)


@login_required
@require_POST
def preview_content(request):
    """Rendu serveur du BBCode, identique à celui de la page article."""
    content = request.POST.get('content', '')
    html = render_to_string('posts/_post_body.html', {'content': content})
    return JsonResponse({'html': html})


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
            "Tu ne dois JAMAIS utiliser de markdown."
            "Tu utilises du BBCode pour le formatage si nécessaire : [b], [i], [t2], [t3], [quote], etc\n\n"
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