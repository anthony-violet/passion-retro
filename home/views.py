import re

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from posts.models import Post

def home(request):
    edito = Post.objects.filter(type='edito', active=True).first()
    news = Post.objects.filter(type='news', active=True).order_by('-created')[:6]

    context = {
        'edito': edito,
        'news': news,
    }

    return render(request, "home.html", context)

def discover(request):
    latest_posts = (
        Post.objects.filter(active=True)
        .exclude(type='edito')
        .order_by('-created')[:3]
    )

    context = {
        'latest_posts': latest_posts,
        'page_title': f"Découvrir {settings.SITE_NAME} - La communauté rétro francophone",
        'page_heading': f"Découvrir {settings.SITE_NAME}",
        'page_description': (
            f"Découvrez {settings.SITE_NAME} : un magazine participatif, un forum, "
            "des jeux rétro, des quiz et une communauté francophone passionnée."
        ),
    }

    return render(request, "discover.html", context)

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