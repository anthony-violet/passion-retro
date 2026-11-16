"""Règles métier du Mur des souvenirs : XP, époque d'un membre, souvenir du jour."""

from datetime import timedelta

from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from users.leveling import grant_experience

from .models import Memory, MemoryComment

XP_MEMORY_PUBLISHED = 25
XP_COMMENT = 5
COMMENT_XP_MIN_LENGTH = 80
COMMENT_XP_DAILY_LIMIT = 3


def grant_memory_xp(memory):
    """XP accordée une seule fois, au moment où le souvenir est validé."""
    if memory.xp_granted:
        return 0
    levels = grant_experience(memory.author, XP_MEMORY_PUBLISHED)
    Memory.objects.filter(pk=memory.pk).update(xp_granted=True)
    memory.xp_granted = True
    return levels


def grant_comment_xp(comment):
    """XP pour un commentaire assez développé, plafonnée par jour.

    Les réactions et les favoris ne rapportent jamais d'XP : on récompense
    le fait de raconter quelque chose, pas les clics.
    """
    if comment.xp_granted:
        return False
    if len(comment.content.strip()) < COMMENT_XP_MIN_LENGTH:
        return False
    if comment.memory.author_id == comment.author_id:
        return False

    since = timezone.now() - timedelta(days=1)
    rewarded_today = MemoryComment.objects.filter(
        author=comment.author, xp_granted=True, created_at__gte=since
    ).count()
    if rewarded_today >= COMMENT_XP_DAILY_LIMIT:
        return False

    grant_experience(comment.author, XP_COMMENT)
    MemoryComment.objects.filter(pk=comment.pk).update(xp_granted=True)
    comment.xp_granted = True
    return True


def era_for_user(user):
    """Époque de l'enfance d'un membre, déduite de sa date de naissance.

    On considère que les souvenirs marquants se forment vers 10 ans.
    """
    birth_date = getattr(user, 'birth_date', None)
    if not birth_date:
        return None
    childhood = birth_date.year + 10
    if childhood < 1990:
        return Memory.ERA_80S
    if childhood < 2000:
        return Memory.ERA_90S
    if childhood < 2010:
        return Memory.ERA_00S
    return Memory.ERA_OTHER


def memory_of_the_day(today=None):
    """Ressort chaque jour un souvenir publié il y a au moins un an.

    Le choix est déterministe pour la journée : tout le monde voit le même.
    """
    today = today or timezone.localdate()
    one_year_ago = timezone.now() - timedelta(days=365)
    ids = list(
        Memory.objects.filter(
            status=Memory.STATUS_PUBLISHED, published_at__lte=one_year_ago
        ).order_by('pk').values_list('pk', flat=True)
    )
    if not ids:
        return None
    pk = ids[today.toordinal() % len(ids)]
    return Memory.objects.select_related('author').get(pk=pk)


def redirect_next(request, fallback):
    """Redirige vers « next » uniquement s'il pointe vers ce site."""
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(fallback)
