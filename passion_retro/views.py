from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render


def custom_404(request, exception):
    return render(request, "errors/404.html", status=404)


def robots_txt(request):
    base = settings.SITE_URL.rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /panel/",
        "Disallow: /pm/",
        "Disallow: /gallery/",
        "Disallow: /quiz/",
        "Disallow: /shop/",
        "Disallow: /users/login/",
        "Disallow: /users/register/",
        "Disallow: /users/activate/",
        "Disallow: /users/profile/update/",
        "Disallow: /users/profile/contributions/",
        "Disallow: /users/contribute/",
        "Disallow: /games/bac/party",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def llms_txt(request):
    base = settings.SITE_URL.rstrip("/")
    site_name = settings.SITE_NAME
    content = f"""# {site_name}

> Communauté francophone dédiée à la culture rétro : jeux vidéo, films, séries, musique et technologies des années 70 à 90.

## Sections principales

- [Accueil]({base}/) : éditorial et dernières actualités.
- [Forum]({base}/forum/) : discussions communautaires sur la culture rétro.
- [Éphémérides rétro]({base}/ephemerides/) : événements marquants survenus à la date du jour.
- [Portail des jeux]({base}/games/) : jeux en ligne créés par la communauté.
- [Livre d'or]({base}/guestbook/) : messages des visiteurs.
- [Fil d'actualités (JSON)]({base}/api/news/) : titres, dates et extraits des dernières actualités.

## À propos

{site_name} est un site communautaire francophone consacré à la nostalgie des années 80 et 90.
Les contenus éditoriaux sont rédigés par la communauté et validés par l'équipe du site.
"""
    return HttpResponse(content, content_type="text/plain; charset=utf-8")
