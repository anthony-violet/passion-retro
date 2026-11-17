"""Décors thématiques et éditions spéciales (Noël, édition Vice City…).

Les périodes se règlent dans le panel (home.models.SeasonalEvent). Chaque
visiteur peut masquer un décor depuis le footer : ce choix est gardé dans un
cookie propre à chaque décor.

- Noël : une couche (neige, guirlande, bonnet, sapins) posée sur tous les thèmes.
- Vice City : un thème temporaire « vicecity » imposé à tout le site pendant la
  période, sans toucher au thème enregistré des membres.
"""
from datetime import date

from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.http import require_POST

COOKIE_MAX_AGE = 60 * 60 * 24 * 120
OPT_OUT_COOKIES = {
    "christmas": "xmas_decor_off",
    "vicecity": "vice_edition_off",
}
SPECIAL_EDITION_THEME = "vicecity"


def event_active(key: str, today: date | None = None) -> bool:
    from home.models import SeasonalEvent

    return SeasonalEvent.get(key).is_active(today or timezone.localdate())


def opted_out(request, key: str) -> bool:
    return request.COOKIES.get(OPT_OUT_COOKIES[key]) == "1"


class SpecialEditionThemeMiddleware(MiddlewareMixin):
    """Impose le thème de l'édition spéciale pendant sa période.

    Placé après UserStatsMiddleware (qui choisit le thème du visiteur) : on ne
    remplace que request.theme_active, jamais le thème enregistré du membre.
    """

    def process_request(self, request):
        active = event_active("vicecity")
        request.special_edition_active = active
        request.special_edition_enabled = active and not opted_out(request, "vicecity")
        if request.special_edition_enabled:
            request.theme_active = SPECIAL_EDITION_THEME


def seasonal_context(request):
    christmas = event_active("christmas")
    vice = getattr(request, "special_edition_active", None)
    if vice is None:  # middleware absent (ex. tests)
        vice = event_active("vicecity")
    return {
        "christmas_active": christmas,
        "christmas_enabled": christmas and not opted_out(request, "christmas"),
        "vice_active": vice,
        "vice_enabled": getattr(request, "special_edition_enabled", False),
    }


@require_POST
def toggle_event(request, key):
    """Masque ou réaffiche un décor pour ce navigateur."""
    if key not in OPT_OUT_COOKIES:
        raise Http404
    cookie = OPT_OUT_COOKIES[key]
    disable = request.COOKIES.get(cookie) != "1"
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        response = JsonResponse({"enabled": not disable})
    else:
        target = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            target = "/"
        response = redirect(target)
    if disable:
        response.set_cookie(cookie, "1", max_age=COOKIE_MAX_AGE, samesite="Lax", secure=request.is_secure())
    else:
        response.delete_cookie(cookie, samesite="Lax")
    return response
