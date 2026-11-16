import re

from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from posts.models import Post
from wall_memories.models import Memory
from wall_memories.services import memory_of_the_day

def home(request):
    edito = Post.objects.filter(type='edito', active=True).first()
    news = Post.objects.filter(type='news', active=True).order_by('-created')[:6]

    # Mise en avant du Mur des souvenirs : le souvenir du jour, sinon le dernier publié.
    daily_memory = memory_of_the_day()
    featured_memory = daily_memory or (
        Memory.objects.filter(status=Memory.STATUS_PUBLISHED)
        .select_related('author').order_by('-published_at').first()
    )

    context = {
        'edito': edito,
        'news': news,
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


def news_list(request):
    """Liste paginée de toutes les actus actives, de la plus récente à la plus ancienne."""
    news = (
        Post.objects.filter(type='news', active=True)
        .select_related('author')
        .order_by('-created')
    )
    paginator = Paginator(news, NEWS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_title = f"Toutes les actus - {settings.SITE_NAME}"
    if page_obj.number > 1:
        page_title = f"Toutes les actus (page {page_obj.number}) - {settings.SITE_NAME}"

    context = {
        'news': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'page_title': page_title,
        'page_description': (
            f"Toutes les actus rétro de {settings.SITE_NAME} : jeux vidéo, films, "
            "séries et culture des années 80 et 90, proposées par la communauté."
        ),
    }

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