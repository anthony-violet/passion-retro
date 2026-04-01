from django.conf import settings
from .theme_config import get_theme_config, get_layout_config


def theme_context(request):
    if not hasattr(request, "theme_active"):
        return {}

    config = get_theme_config(request.theme_active)
    layout = get_layout_config(request.theme_active)

    return {
        "theme_config": config,
        "theme_layout": layout,
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL,
    }
