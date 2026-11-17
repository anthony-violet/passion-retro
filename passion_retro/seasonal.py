"""Décors thématiques et éditions spéciales (Noël, éditions Vice City et Doomsday…).

Les périodes se règlent dans le panel (home.models.SeasonalEvent). Chaque
visiteur peut masquer un décor depuis le footer : ce choix est gardé dans un
cookie propre à chaque décor.

- Noël : une couche (neige, guirlande, bonnet, sapins) posée sur tous les thèmes.
- Éditions spéciales (Vice City, Doomsday) : un thème temporaire imposé à tout
  le site pendant la période, sans toucher au thème enregistré des membres.
  Une seule à la fois : si deux périodes se chevauchent, la première de
  SPECIAL_EDITIONS l'emporte.
"""
from datetime import date

from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.http import require_POST

COOKIE_MAX_AGE = 60 * 60 * 24 * 120

# Éditions spéciales, par ordre de priorité. « theme » est le dossier
# static/themes/<theme>/ et la clé de passion_retro.theme_config.
SPECIAL_EDITIONS = {
    "doomsday": {"theme": "doomsday", "cookie": "doom_edition_off", "icon": "🛡️"},
    "vicecity": {"theme": "vicecity", "cookie": "vice_edition_off", "icon": "🌴"},
}
OPT_OUT_COOKIES = {
    "christmas": "xmas_decor_off",
    **{key: edition["cookie"] for key, edition in SPECIAL_EDITIONS.items()},
}

# Sortie d'Avengers: Doomsday dans les salles françaises (compte à rebours).
DOOMSDAY_RELEASE = date(2026, 12, 16)


def event_active(key: str, today: date | None = None) -> bool:
    from home.models import SeasonalEvent

    return SeasonalEvent.get(key).is_active(today or timezone.localdate())


def opted_out(request, key: str) -> bool:
    return request.COOKIES.get(OPT_OUT_COOKIES[key]) == "1"


def current_special_edition(request, today: date | None = None):
    """(clé de l'édition spéciale en cours ou None, affichée pour ce visiteur ?)"""
    for key in SPECIAL_EDITIONS:
        if event_active(key, today):
            return key, not opted_out(request, key)
    return None, False


class SpecialEditionThemeMiddleware(MiddlewareMixin):
    """Impose le thème de l'édition spéciale pendant sa période.

    Placé après UserStatsMiddleware (qui choisit le thème du visiteur) : on ne
    remplace que request.theme_active, jamais le thème enregistré du membre.
    """

    def process_request(self, request):
        key, enabled = current_special_edition(request)
        request.special_edition = key
        request.special_edition_active = key is not None
        request.special_edition_enabled = enabled
        if enabled:
            request.theme_active = SPECIAL_EDITIONS[key]["theme"]


def seasonal_context(request):
    christmas = event_active("christmas")
    if hasattr(request, "special_edition"):
        edition, enabled = request.special_edition, request.special_edition_enabled
    else:  # middleware absent (ex. tests) : on affiche le bouton, sans imposer le thème
        edition, enabled = current_special_edition(request)[0], False
    return {
        "christmas_active": christmas,
        "christmas_enabled": christmas and not opted_out(request, "christmas"),
        "special_edition": edition,
        "special_edition_enabled": enabled,
        "special_edition_icon": SPECIAL_EDITIONS[edition]["icon"] if edition else "",
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
