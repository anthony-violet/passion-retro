from .models import MysteryAttempt, MysteryGame


def mystery_widget(request):
    """Jeu mystère du jour pour l'encart de la colonne de droite.

    Fourni sous forme de fonction : la requête n'est faite que si l'encart
    est réellement affiché.
    """
    def widget():
        from . import mystery

        game = mystery.today_game()
        if game is None:
            return None
        clues = list(game.clues.all())
        if not clues:
            return None
        user = getattr(request, 'user', None)
        attempt = None
        if user is not None and user.is_authenticated:
            attempt = MysteryAttempt.objects.filter(user=user, game=game).first()
        return {
            'first_clue': clues[0],
            'clues_total': len(clues),
            'attempt': attempt,
            'is_author': mystery.is_author(user, game) if user is not None else False,
            'max_xp': mystery.rewards_for(1, len(clues))[0],
            'winners': game.attempts.filter(status=MysteryAttempt.STATUS_WON).count(),
        }

    return {'mystery_widget': widget}


def pending_mystery_count(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_staff:
        return {'pending_mystery_count': 0}
    return {
        'pending_mystery_count': MysteryGame.objects.filter(status=MysteryGame.STATUS_PENDING).count()
    }
