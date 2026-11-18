import re

from django.utils import timezone
from django.utils.dateformat import format as date_format

from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from posts.models import Category, Post
from posts.news import latest_reactions, news_queryset
from wall_memories.models import Memory
from wall_memories.services import memory_of_the_day

HOME_NEWS_CARDS = 4


def home(request):
    edito = Post.objects.filter(type='edito', active=True).first()
    news = news_queryset()
    featured_news = news.filter(featured=True).first() or news.first()
    news_cards = list(news.exclude(pk=featured_news.pk)[:HOME_NEWS_CARDS]) if featured_news else []
    news_buzz = list(news.filter(reactions__gt=0).order_by('-last_activity')[:3])
    news_prompt = next(
        (n for n in [featured_news, *news_cards] if n and n.forum_prompt), None
    )
    featured_last_reaction = latest_reactions(featured_news, 1) if featured_news else []

    # Mise en avant du Mur des souvenirs : le souvenir du jour, sinon le dernier publié.
    daily_memory = memory_of_the_day()
    featured_memory = daily_memory or (
        Memory.objects.filter(status=Memory.STATUS_PUBLISHED)
        .select_related('author').order_by('-published_at').first()
    )

    context = {
        'edito': edito,
        'featured_news': featured_news,
        'news_cards': news_cards,
        'news_buzz': news_buzz,
        'news_prompt': news_prompt,
        'featured_last_reaction': featured_last_reaction[0] if featured_last_reaction else None,
        'featured_memory': featured_memory,
        'featured_memory_is_daily': daily_memory is not None,
    }

    return render(request, "home.html", context)

def discover(request):
    latest_posts = (
        Post.objects.filter(active=True)
        .exclude(type='edito')
        .order_by('-created')[:3]
    )

    latest_memories = (
        Memory.objects.filter(status=Memory.STATUS_PUBLISHED)
        .select_related('author').order_by('-published_at')[:3]
    )

    context = {
        'latest_posts': latest_posts,
        'latest_memories': latest_memories,
        'page_title': f"Découvrir {settings.SITE_NAME} - La communauté rétro francophone",
        'page_heading': f"Découvrir {settings.SITE_NAME}",
        'page_description': (
            f"Découvrez {settings.SITE_NAME} : un magazine participatif, un forum, "
            "le Mur des souvenirs, des jeux rétro, des quiz et une communauté "
            "francophone passionnée."
        ),
    }

    return render(request, "discover.html", context)

NEWS_PER_PAGE = 12


NEWS_SORTS = {
    'recent': ('Plus récentes', ('-pub_date', '-pk')),
    'commentees': ('Plus commentées', ('-reactions', '-pub_date')),
    'actives': ('Discussions actives', ('-last_activity', '-pub_date')),
}


def news_list(request):
    """Liste paginée des actus actives, filtrable par catégorie et triable."""
    news = news_queryset()
    categories = list(
        Category.objects.filter(pk__in=news.values('category_id')).order_by('name')
    )
    current_cat = next((c for c in categories if str(c.pk) == request.GET.get('cat')), None)
    if current_cat:
        news = news.filter(category=current_cat)
    sort = request.GET.get('tri') if request.GET.get('tri') in NEWS_SORTS else 'recent'
    if sort == 'actives':
        news = news.filter(last_activity__isnull=False)
    news = news.order_by(*NEWS_SORTS[sort][1])

    paginator = Paginator(news, NEWS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Regroupement par mois de publication (tri chronologique uniquement).
    groups = []
    for post in page_obj:
        label = date_format(timezone.localtime(post.pub_date), 'F Y').capitalize() if sort == 'recent' else ''
        if not groups or groups[-1][0] != label:
            groups.append((label, []))
        groups[-1][1].append(post)

    page_title = f"Toutes les actus - {settings.SITE_NAME}"
    if page_obj.number > 1:
        page_title = f"Toutes les actus (page {page_obj.number}) - {settings.SITE_NAME}"

    context = {
        'news': page_obj,
        'news_groups': groups,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'categories': categories,
        'current_cat': current_cat,
        'sort': sort,
        'sorts': [(key, label) for key, (label, _) in NEWS_SORTS.items()],
        'page_title': page_title,
        'page_description': (
            f"Toutes les actus rétro de {settings.SITE_NAME} : jeux vidéo, films, "
            "séries et culture des années 80 et 90, proposées par la communauté."
        ),
    }
    if current_cat or sort != 'recent':
        context['seo_noindex'] = True

    return render(request, "news_list.html", context)


def api_news(request):
    try:
        limit = min(max(int(request.GET.get("limit", 4)), 1), 20)
    except ValueError:
        limit = 4

    news = Post.objects.filter(type="news", active=True).order_by("-created")[:limit]
    items = []
    for post in news:
        excerpt = re.sub(r"\[[^\]]*\]", " ", post.content or "")
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        if len(excerpt) > 170:
            excerpt = excerpt[:169].rstrip() + "…"
        items.append(
            {
                "slug": post.slug,
                "title": post.title,
                "created": post.created.isoformat(),
                "excerpt": excerpt,
            }
        )

    return JsonResponse({"items": items})


def custom_404(request, exception):
    return render(request, "errors/404.html", status=404)