from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404


def rpg_is_visible(user):
    """Ivakar reste réservé au staff tant que ``RPG_OPEN`` n'est pas activé."""
    return getattr(settings, 'RPG_OPEN', False) or bool(getattr(user, 'is_staff', False))


def rpg_access(view_func):
    """Page publique du RPG : 404 tant que le jeu n'est pas ouvert (sauf staff)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not rpg_is_visible(request.user):
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper


def rpg_player(view_func):
    """Page de jeu : membre connecté, jeu visible pour lui."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if not getattr(settings, 'RPG_OPEN', False):
                raise Http404
            return redirect_to_login(request.get_full_path())
        if not rpg_is_visible(request.user):
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper
