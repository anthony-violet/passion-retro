from . import announcements


def announcement_banner(request):
    """Bandeau « Nouveauté ! » tant que le visiteur ou le membre ne l'a pas fermé."""
    current = announcements.current()
    if not current or request.path.startswith(('/nouveautes/', '/panel/', '/admin/')):
        return {'announcement_banner': None}
    if announcements.banner_closed(request):
        return {'announcement_banner': None}
    return {'announcement_banner': current}
