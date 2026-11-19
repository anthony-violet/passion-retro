from urllib.parse import urlencode

from django.conf import settings
from django.templatetags.static import static

from .seo import organization_jsonld, website_jsonld
from .theme_config import get_theme_config, get_layout_config


NOINDEX_PREFIXES = (
    "/admin/",
    "/panel/",
    "/pm/",
    "/gallery/",
    "/quiz/",
    "/shop/",
    "/users/login/",
    "/users/register/",
    "/users/activate/",
    "/users/profile/update/",
    "/users/profile/contributions/",
    "/users/contribute/",
    "/users/new/feature",
    "/users/item/",
    "/games/bac/party",
)

ANALYTICS_PRIVATE_PREFIXES = (
    "/admin",
    "/panel",
    "/pm",
    "/users/activate",
    "/users/profile",
    "/users/contributions",
    "/users/item",
    "/users/new/feature",
)

DEFAULT_TITLE = (
    f"{settings.SITE_NAME} - Communauté des Passionnés de Jeux, Films et Séries Rétro"
)
DEFAULT_DESCRIPTION = (
    f"Rejoignez {settings.SITE_NAME}, la communauté dédiée aux passionnés de jeux, "
    "films et séries des années 80 et 90. Découvrez des contenus exclusifs et "
    "partagez votre passion !"
)


def theme_context(request):
    # Le panel d'administration occupe toute la largeur, sans colonnes latérales.
    full_width_page = request.path.startswith("/panel/")
    if not hasattr(request, "theme_active"):
        return {"full_width_page": full_width_page}

    config = get_theme_config(request.theme_active)
    layout = get_layout_config(request.theme_active)

    return {
        "full_width_page": full_width_page,
        "theme_config": config,
        "theme_layout": layout,
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL,
    }


def _canonical_url(request):
    url = request.build_absolute_uri(request.path)
    page = request.GET.get("page") if hasattr(request, "GET") else None
    # Seul un numéro de page entier > 1 est conservé : ?page=1, ?page=abc,
    # ?page=01… pointent tous vers l'URL sans paramètre.
    if page and page.isdigit() and int(page) > 1:
        url = f"{url}?{urlencode({'page': int(page)})}"
    return url


def seo_context(request):
    return {
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL,
        "page_title": DEFAULT_TITLE,
        "page_heading": settings.SITE_NAME,
        "page_description": DEFAULT_DESCRIPTION,
        "seo_canonical": _canonical_url(request),
        "seo_og_image": request.build_absolute_uri(static("img/retrobot.png")),
        "seo_og_type": "website",
        "seo_noindex": request.path.startswith(NOINDEX_PREFIXES),
        "seo_organization_jsonld": organization_jsonld(),
        "seo_website_jsonld": website_jsonld(),
        "seo_page_jsonld": "",
    }


def analytics_context(request):
    container_id = getattr(settings, "GTM_CONTAINER_ID", "") or ""
    user = getattr(request, "user", None)
    is_authenticated = bool(getattr(user, "is_authenticated", False))
    path = getattr(request, "path", "") or ""
    tracking = bool(
        container_id
        and not settings.DEBUG
        and not is_authenticated
        and not path.startswith(ANALYTICS_PRIVATE_PREFIXES)
    )
    return {
        "gtm_container_id": container_id,
        "analytics_tracking": tracking,
    }
