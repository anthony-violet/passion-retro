"""Annonce de nouveauté en cours.

Une seule annonce est active à la fois. Pour en publier une nouvelle, il suffit
de changer ``CURRENT`` (une nouvelle ``key`` la remontre à tous les membres).
Mettre ``CURRENT = None`` désactive la redirection et le bandeau.
"""

from django.contrib.auth import get_user_model

from users.leveling import grant_experience

CURRENT = {
    'key': '2026-11-profil-et-mur-des-souvenirs',
    'title': 'Profil enrichi et Mur des souvenirs',
    'banner': 'Nouveauté : le Mur des souvenirs est ouvert, et ton profil s\'enrichit !',
    'template': 'features/new_feature_user_profile_and_wall_of_memories.html',
    'xp': 50,
}

BANNER_COOKIE = 'pr_announcement_closed'

# Chemins sur lesquels on ne redirige jamais vers l'annonce.
EXCLUDED_PREFIXES = (
    '/nouveautes/', '/admin/', '/panel/', '/static/', '/media/', '/api/',
    '/users/new/feature', '/users/logout/', '/logout/', '/maintenance/',
    '/sitemap.xml', '/robots.txt', '/llms.txt',
)


def current():
    return CURRENT


def has_seen(user):
    announcement = current()
    return not announcement or user.last_announcement_seen == announcement['key']


def mark_seen(user):
    """Marque l'annonce comme vue et offre le cadeau, une seule fois.

    Renvoie le nombre d'XP offerts (0 si l'annonce avait déjà été vue).
    """
    announcement = current()
    if not announcement or not user.is_authenticated:
        return 0
    updated = get_user_model().objects.filter(pk=user.pk).exclude(
        last_announcement_seen=announcement['key']
    ).update(last_announcement_seen=announcement['key'])
    user.last_announcement_seen = announcement['key']
    if not updated:
        return 0
    xp = announcement.get('xp') or 0
    if xp:
        grant_experience(user, xp)
    return xp


def banner_closed(request):
    announcement = current()
    if not announcement:
        return True
    user = request.user
    if user.is_authenticated and user.announcement_banner_closed == announcement['key']:
        return True
    return request.COOKIES.get(BANNER_COOKIE) == announcement['key']
