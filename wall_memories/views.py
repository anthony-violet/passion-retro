import random
from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MemoryCommentForm, MemoryForm
from .models import Console, Memory, MemoryComment, MemoryFavorite, MemoryReaction
from .services import era_for_user, grant_comment_xp, memory_of_the_day, redirect_next

PER_PAGE = 12
RANDOM_COUNT = 9

# Chaque thème a ses propres templates ; un thème inconnu retombe sur « default ».
THEMES = {'default', '00s', 'modern', '80s', 'retrogame', 'retrorpg', 'rpg', 'vhs'}
# Thèmes affichés en fil vertical plutôt qu'en mosaïque.
FEED_THEMES = {'modern'}

SORTS = [
    ('recent', 'Les plus récents'),
    ('liked', 'Les plus appréciés'),
    ('commented', 'Les plus commentés'),
    ('era', 'Les souvenirs de mon époque'),
    ('random', 'Les souvenirs au hasard'),
]


def _theme(request):
    theme = getattr(request, 'theme_active', None) or getattr(request.user, 'theme', 'default')
    return theme if theme in THEMES else 'default'


def _render(request, name, context):
    theme = _theme(request)
    # La fenêtre de publication est présente sur toutes les pages du Mur :
    # elle a toujours besoin d'un formulaire (sauf s'il est déjà fourni, avec ses erreurs).
    if request.user.is_authenticated:
        context.setdefault('form', MemoryForm())
    context.update({
        'wm_theme': theme,
        'wm_masonry': theme not in FEED_THEMES,
        'wm_card': f'wall_memories/{theme}/card.html',
        'wm_form': f'wall_memories/{theme}/form_modal.html',
        'reaction_types': [
            (value, MemoryReaction.EMOJIS[value], label)
            for value, label in MemoryReaction.TYPE_CHOICES
        ],
    })
    return render(request, [
        f'wall_memories/{theme}/{name}',
        f'wall_memories/default/{name}',
    ], context)


def _published():
    return (
        Memory.objects.filter(status=Memory.STATUS_PUBLISHED)
        .select_related('author__featured_collectible')
        .prefetch_related('consoles', 'author__levels')
    )


def decorate(memories, user):
    """Ajoute à chaque souvenir le résumé des réactions et l'état du membre."""
    memories = list(memories)
    ids = [m.pk for m in memories]
    if not ids:
        return memories

    counts = defaultdict(dict)
    for row in (
        MemoryReaction.objects.filter(memory_id__in=ids)
        .values('memory_id', 'type')
        .annotate(total=Count('id'))
    ):
        counts[row['memory_id']][row['type']] = row['total']

    mine = defaultdict(set)
    favorites = set()
    if user.is_authenticated:
        for memory_id, rtype in MemoryReaction.objects.filter(
            memory_id__in=ids, user=user
        ).values_list('memory_id', 'type'):
            mine[memory_id].add(rtype)
        favorites = set(
            MemoryFavorite.objects.filter(memory_id__in=ids, user=user)
            .values_list('memory_id', flat=True)
        )

    for memory in memories:
        memory.reaction_summary = [
            {
                'type': value,
                'emoji': MemoryReaction.EMOJIS[value],
                'label': label,
                'count': counts[memory.pk].get(value, 0),
                'mine': value in mine[memory.pk],
            }
            for value, label in MemoryReaction.TYPE_CHOICES
        ]
        memory.is_favorite = memory.pk in favorites
    return memories


def _query_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def wall(request):
    sort = request.GET.get('tri', 'recent')
    if sort not in dict(SORTS):
        sort = 'recent'
    era = request.GET.get('epoque', '')
    console_slug = request.GET.get('console', '')

    qs = _published()
    if era in dict(Memory.ERA_CHOICES):
        qs = qs.filter(era=era)
    else:
        era = ''
    console = None
    if console_slug:
        console = Console.objects.filter(slug=console_slug).first()
        if console:
            qs = qs.filter(consoles=console)

    user_era = era_for_user(request.user) if request.user.is_authenticated else None
    era_missing = False
    page_obj = None

    if sort == 'random':
        ids = list(qs.values_list('pk', flat=True))
        picked = random.sample(ids, min(RANDOM_COUNT, len(ids)))
        memories = list(qs.filter(pk__in=picked))
        random.shuffle(memories)
    else:
        if sort == 'liked':
            qs = qs.order_by('-reactions_count', '-published_at')
        elif sort == 'commented':
            qs = qs.order_by('-comments_count', '-published_at')
        elif sort == 'era':
            if user_era:
                qs = qs.filter(era=user_era)
            else:
                era_missing = True
            qs = qs.order_by('-published_at')
        else:
            qs = qs.order_by('-published_at')
        page_obj = Paginator(qs, PER_PAGE).get_page(request.GET.get('page'))
        memories = page_obj.object_list

    published = Memory.objects.filter(status=Memory.STATUS_PUBLISHED)
    daily = memory_of_the_day()

    return _render(request, 'wall.html', {
        'memories': decorate(memories, request.user),
        'page_obj': page_obj,
        'query_string': _query_without_page(request),
        'sort': sort,
        'sorts': SORTS,
        'era': era,
        'eras': Memory.ERA_CHOICES,
        'user_era': user_era,
        'era_missing': era_missing,
        'console': console,
        'consoles': Console.objects.filter(is_active=True),
        'total_memories': published.count(),
        'total_contributors': published.values('author').distinct().count(),
        'memory_of_the_day': decorate([daily], request.user)[0] if daily else None,
        'form': MemoryForm(),
        'page_title': f"Le Mur des souvenirs - {settings.SITE_NAME}",
        'page_description': (
            "Parce que certains souvenirs ne s'effacent jamais : les membres "
            "racontent les moments de jeu vidéo qui ont marqué leur enfance."
        ),
    })


def _can_view(memory, user):
    if memory.is_published:
        return True
    return user.is_authenticated and (user == memory.author or user.is_staff)


def detail(request, pk, slug=None):
    memory = get_object_or_404(
        Memory.objects.select_related('author').prefetch_related('consoles'), pk=pk
    )
    if not _can_view(memory, request.user):
        raise Http404
    if slug != memory.slug:
        return redirect(memory.get_absolute_url(), permanent=True)

    comments = (
        memory.comments.filter(status=MemoryComment.STATUS_PUBLISHED)
        .select_related('author__featured_collectible')
        .prefetch_related('author__levels')
    )
    others = (
        _published().filter(author=memory.author).exclude(pk=memory.pk)
        .order_by('-published_at')[:3]
    )

    return _render(request, 'detail.html', {
        'memory': decorate([memory], request.user)[0],
        'comments': comments,
        'comment_form': MemoryCommentForm(),
        'other_memories': others,
        'page_title': f"{memory.title} - Le Mur des souvenirs - {settings.SITE_NAME}",
        'page_description': memory.content[:155],
        'seo_noindex': not memory.is_published,
    })


@login_required
def create(request):
    if request.method == 'POST':
        form = MemoryForm(request.POST, request.FILES)
        if form.is_valid():
            memory = form.save(commit=False)
            memory.author = request.user
            memory.status = Memory.STATUS_PENDING
            memory.save()
            form.save_m2m()
            messages.success(
                request,
                "Merci pour ton souvenir ❤️ Il sera publié sur le Mur dès qu'un "
                "membre de l'équipe l'aura relu.",
            )
            return redirect('wall_memories:mine')
    else:
        form = MemoryForm()
    return _render(request, 'create.html', {
        'form': form,
        'page_title': f"Partager un souvenir - {settings.SITE_NAME}",
        'seo_noindex': True,
    })


@login_required
def edit(request, pk):
    memory = get_object_or_404(Memory, pk=pk)
    if memory.author != request.user and not request.user.is_staff:
        raise Http404
    # Un membre ne peut retoucher que ce qui n'est pas encore publié.
    if memory.is_published and not request.user.is_staff:
        messages.error(request, "Un souvenir publié ne peut plus être modifié.")
        return redirect(memory.get_absolute_url())

    if request.method == 'POST':
        form = MemoryForm(request.POST, request.FILES, instance=memory)
        if form.is_valid():
            memory = form.save(commit=False)
            if memory.status == Memory.STATUS_REJECTED:
                memory.status = Memory.STATUS_PENDING
                memory.rejection_reason = ''
            memory.save()
            form.save_m2m()
            messages.success(request, "Ton souvenir a été mis à jour.")
            return redirect('wall_memories:mine')
    else:
        form = MemoryForm(instance=memory)
    return _render(request, 'create.html', {
        'form': form,
        'memory': memory,
        'page_title': f"Modifier mon souvenir - {settings.SITE_NAME}",
        'seo_noindex': True,
    })


@login_required
@require_POST
def delete(request, pk):
    memory = get_object_or_404(Memory, pk=pk)
    if memory.author != request.user and not request.user.is_staff:
        raise Http404
    memory.delete()
    messages.success(request, "Le souvenir a été supprimé.")
    return redirect('wall_memories:mine')


@login_required
def mine(request):
    memories = (
        Memory.objects.filter(author=request.user)
        .prefetch_related('consoles')
        .order_by('-created_at')
    )
    return _render(request, 'mine.html', {
        'my_memories': memories,
        'page_title': f"Mes souvenirs - {settings.SITE_NAME}",
        'seo_noindex': True,
    })


@login_required
def favorites(request):
    memories = (
        _published().filter(favorites__user=request.user)
        .order_by('-favorites__created_at')
    )
    page_obj = Paginator(memories, PER_PAGE).get_page(request.GET.get('page'))
    return _render(request, 'favorites.html', {
        'memories': decorate(page_obj.object_list, request.user),
        'page_obj': page_obj,
        'query_string': '',
        'page_title': f"Mes souvenirs favoris - {settings.SITE_NAME}",
        'seo_noindex': True,
    })


def _wants_json(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _published_or_404(pk):
    return get_object_or_404(Memory, pk=pk, status=Memory.STATUS_PUBLISHED)


@login_required
@require_POST
def react(request, pk):
    memory = _published_or_404(pk)
    rtype = request.POST.get('type')
    if rtype not in MemoryReaction.EMOJIS:
        return JsonResponse({'error': 'Réaction inconnue.'}, status=400)

    existing = MemoryReaction.objects.filter(memory=memory, user=request.user, type=rtype)
    if existing.exists():
        existing.delete()
        active = False
    else:
        try:
            with transaction.atomic():
                MemoryReaction.objects.create(memory=memory, user=request.user, type=rtype)
        except IntegrityError:
            pass
        active = True
    memory.refresh_counters()

    if _wants_json(request):
        return JsonResponse({
            'active': active,
            'count': memory.reactions.filter(type=rtype).count(),
            'total': memory.reactions_count,
        })
    return redirect_next(request, memory.get_absolute_url())


@login_required
@require_POST
def toggle_favorite(request, pk):
    memory = _published_or_404(pk)
    deleted, _ = MemoryFavorite.objects.filter(memory=memory, user=request.user).delete()
    if not deleted:
        MemoryFavorite.objects.get_or_create(memory=memory, user=request.user)
    active = not deleted

    if _wants_json(request):
        return JsonResponse({'active': active})
    return redirect_next(request, memory.get_absolute_url())


@login_required
@require_POST
def add_comment(request, pk):
    memory = _published_or_404(pk)
    form = MemoryCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.memory = memory
        comment.author = request.user
        comment.save()
        memory.refresh_counters()
        grant_comment_xp(comment)
        return redirect(f"{memory.get_absolute_url()}#comment-{comment.pk}")
    messages.error(request, "Ton commentaire n'a pas pu être publié.")
    return redirect(f"{memory.get_absolute_url()}#comments")


@login_required
@require_POST
def delete_comment(request, pk):
    comment = get_object_or_404(MemoryComment.objects.select_related('memory'), pk=pk)
    if comment.author != request.user and not request.user.is_staff:
        raise Http404
    memory = comment.memory
    comment.delete()
    memory.refresh_counters()
    messages.success(request, "Commentaire supprimé.")
    return redirect(f"{memory.get_absolute_url()}#comments")


def random_memory(request):
    """Redirige vers un souvenir au hasard (bouton « Surprends-moi »)."""
    ids = list(
        Memory.objects.filter(status=Memory.STATUS_PUBLISHED).values_list('pk', flat=True)
    )
    if not ids:
        return redirect('wall_memories:wall')
    memory = Memory.objects.get(pk=random.choice(ids))
    return redirect(memory.get_absolute_url())
