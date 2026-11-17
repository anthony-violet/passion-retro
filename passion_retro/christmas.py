"""Décor de Noël saisonnier, piloté depuis le panel (home.models.ChristmasSettings).

Les dates (jour/mois, répétées chaque année) et le mode (automatique, toujours
activé, désactivé) se règlent dans le panel. Chaque visiteur peut masquer le
décor depuis le footer ; ce choix est gardé dans un cookie.
"""
from datetime import date

from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

COOKIE_NAME = "xmas_decor_off"
COOKIE_MAX_AGE = 60 * 60 * 24 * 120  # couvre largement une saison


def christmas_active(today: date | None = None) -> bool:
    from home.models import ChristmasSettings

    return ChristmasSettings.load().is_active(today or timezone.localdate())


def christmas_context(request):
    active = christmas_active()
    return {
        "christmas_active": active,
        "christmas_enabled": active and request.COOKIES.get(COOKIE_NAME) != "1",
    }


@require_POST
def toggle_christmas(request):
    """Active ou désactive le décor pour ce navigateur."""
    disable = request.COOKIES.get(COOKIE_NAME) != "1"
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
        response.set_cookie(
            COOKIE_NAME, "1", max_age=COOKIE_MAX_AGE, samesite="Lax", secure=request.is_secure()
        )
    else:
        response.delete_cookie(COOKIE_NAME, samesite="Lax")
    return response
