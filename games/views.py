from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import *
from .models import MysteryAttempt
from users.leveling import grant_experience
from django.utils.timezone import now
from django.contrib import messages
from django.db.models import Count, Sum
from django.db.models.functions import Lower

def portal(request):
    from quiz.models import Quiz

    from . import mystery

    meta = {
        'page_title': f"Portail des Jeux - {settings.SITE_NAME}",
        'page_heading': "Portail des Jeux",
        'page_description': (
            "Jouez en ligne aux jeux rétro de la communauté : jeu mystère du jour, "
            "Petit Bac, quiz et défis entre membres."
        ),
    }
    today_mystery = mystery.today_game()
    mystery_attempt = None
    if today_mystery and request.user.is_authenticated:
        mystery_attempt = MysteryAttempt.objects.filter(user=request.user, game=today_mystery).first()

    context = {
        **meta,
        'today_mystery': today_mystery,
        'mystery_attempt': mystery_attempt,
        'mystery_is_author': bool(today_mystery and mystery.is_author(request.user, today_mystery)),
        'mystery_winners': (today_mystery.attempts.filter(status=MysteryAttempt.STATUS_WON).count()
                            if today_mystery else 0),
        'mystery_streak': mystery.streak(request.user) if request.user.is_authenticated else 0,
        'nb_parties': LittleBacGames.objects.filter(status="finished").count(),
        'nb_quizzes': Quiz.objects.filter(is_active=True).count(),
        'games': [],
    }
    if request.user.is_authenticated:
        context['games'] = LittleBacGames.objects.filter(author=request.user, status='waiting')

    from ivakar_rpg.decorators import rpg_is_visible
    from ivakar_rpg.models import Character
    context['rpg_visible'] = rpg_is_visible(request.user)
    context['rpg_open'] = getattr(settings, 'RPG_OPEN', False)
    if context['rpg_visible'] and request.user.is_authenticated:
        context['rpg_character'] = Character.objects.filter(user=request.user).first()
    return render(request, 'games/portal.html', context)


def little_bac_home(request):
    return render(request, 'games/littlebac/home.html', {
        'page_title': f"Le Petit Bac - {settings.SITE_NAME}",
        'page_heading': "Le Petit Bac",
        'page_description': (
            "Jouez au célèbre Petit Bac en ligne avec la communauté : trouvez des "
            "mots par catégorie à partir d'une lettre imposée."
        ),
    })

@login_required()
def little_bac_start(request):
    import random
    import string
    
    game = LittleBacGames.objects.create(name=f"Partie de {request.user.username}", author=request.user)
    LittleBacPlayers.objects.create(
        user=request.user,
        game=game,
        score=0
    )
    
    # Liste des lettres de l'alphabet
    alphabet = string.ascii_uppercase  # 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    # Sélection aléatoire
    random_letter = random.choice(alphabet)

    LittleBacRounds.objects.create(
        game=game,
        letter=random_letter,
        round_counter=1
    )

    return redirect('bac_party_games', party_id=game.id)

@login_required()
def little_bac_party(request, party_id):
    game = get_object_or_404(LittleBacGames, id=party_id)
    players = LittleBacPlayers.objects.filter(game=game).select_related(
        'user'
    ).prefetch_related('user__levels')
    rounds = LittleBacRounds.objects.filter(game=game)
    
    if players.filter(user=request.user).exists():
        current_round = rounds.last()
        return render(request, 'games/littlebac/game.html', {'game': game, 'players': players, 'round': current_round})
    else:
        return redirect('bac_games')

@login_required()
def little_bac_party_join(request, party_id):
    game = get_object_or_404(LittleBacGames, id=party_id)
    players = LittleBacPlayers.objects.filter(game=game)
    
    if players.filter(user=request.user).exists():
        return redirect('bac_games')

    LittleBacPlayers.objects.create(
        user=request.user,
        game=game,
        score=0
    )

    return redirect('bac_party_games', party_id=game.id)    

@login_required()
def little_bac_party_play(request, party_id):
    game = get_object_or_404(LittleBacGames, id=party_id)
    players = LittleBacPlayers.objects.filter(game=game).select_related(
        'user'
    ).prefetch_related('user__levels')
    
    if not players.filter(user=request.user).exists():
        return redirect('bac_games')

    # Vérifie si la partie est en attente et met à jour le statut
    if game.status == 'waiting':
        game.status = 'in_progress'
        game.save()

    # Récupère le round actuel (dernier round)
    current_round = LittleBacRounds.objects.filter(game=game).last()
    categories = LittleBacCategories.objects.all()
    player = players.get(user=request.user)

    if request.method == "POST":
        # On vérifie que les réponses commencent par la lettre du round
        round_letter = current_round.letter.upper()
        all_valid = True
        for category in categories:
            answer = request.POST.get(f"col-{category.id}", "").strip()
            if answer and answer[0].upper() != round_letter:
                all_valid = False
                break
        
        if all_valid:
            player = LittleBacPlayers.objects.get(game=game, user_id=request.user.id)
            player.status = "overed"
            player.save()

            # Récupérer les réponses soumises par le joueur
            answers = {
                f"col-{category.id}": request.POST.get(f"col-{category.id}")
                for category in categories
            }

            responses = []
            # Enregistre chaque réponse en base de données
            for category in categories:
                answer = answers.get(f"col-{category.id}", "").strip()  # Récupère la réponse ou une chaîne vide
                if answer:  # Vérifie si une réponse est fournie
                    response = LittleBacAnswers.objects.create(
                        round=current_round,
                        player=players.get(user=request.user),
                        category=category,
                        answer=answer,
                        is_valid=False
                    )
                    responses.append(response)

            return render(request, 'games/littlebac/finish.html', {
                'responses': responses, 
                'round': current_round, 
                'categories': categories,
                'player': player
            })
        else:
            messages.error(request, "Les réponses doivent commencer par la lettre du tour.")
            return render(request, 'games/littlebac/play.html', {
                'game': game,
                'round': current_round,
                'categories': categories,
                'countdown_remaining': countdown_remaining,
        })

    # Passe les informations du décompte au template
    countdown_remaining = max(
        0, game.countdown_time - int((now() - game.countdown_start_time).total_seconds())
    ) if game.countdown_started else None

    return render(request, 'games/littlebac/play.html', {
        'game': game,
        'round': current_round,
        'categories': categories,
        'countdown_remaining': countdown_remaining,
        'player': player
    })

@login_required()
def game_little_bac_results(request, party_id):
    game = get_object_or_404(LittleBacGames, id=party_id)
    players = LittleBacPlayers.objects.filter(game=game).select_related(
        'user'
    ).prefetch_related('user__levels')
    rounds = LittleBacRounds.objects.filter(game=game).order_by('round_counter', 'id')
    categories = LittleBacCategories.objects.all()

    all_organized_answers = {}
    scores_by_round = {round.id: {} for round in rounds}
    total_scores = {player.id: 0 for player in players}

    for round in rounds:
        answers = LittleBacAnswers.objects.filter(round=round)

        # On détermine qu'un mot est valide s'il est unique pour une catégorie donnée
        for category in categories:
            valid_answers = answers.filter(category=category).annotate(
                lower_answer=Lower('answer')
            ).values('lower_answer').annotate(
                count=Count('lower_answer')
            ).filter(count=1)
            for answer in valid_answers:
                answers.filter(category=category, answer__iexact=answer['lower_answer']).update(is_valid=True, point=5)

            # Marquer les réponses dupliquées et leur attribuer 1 point
            duplicate_answers = answers.filter(category=category).annotate(
                lower_answer=Lower('answer')
            ).values('lower_answer').annotate(
                count=Count('lower_answer')
            ).filter(count__gt=1)
            for answer in duplicate_answers:
                answers.filter(category=category, answer__iexact=answer['lower_answer']).update(is_valid=False, point=1)

        # Calcule des points pour chaque joueur pour ce round
        for player in players:
            player_score = answers.filter(
                player=player
            ).aggregate(
                total=Sum('point')
            )['total'] or 0

            
            scores_by_round[round.id][player.id] = player_score
            total_scores[player.id] += player_score

            # On ajoute X experience au joueur (X: score du round), une seule
            # fois par round et par joueur (l'idempotence est portée par la base).
            if not round.xp_awarded:
                grant_experience(player.user, player_score)

        if not round.xp_awarded:
            round.xp_awarded = True
            round.save(update_fields=['xp_awarded'])

    # Organiser les réponses par joueur et par catégorie pour chaque round
    for round in rounds:
        answers = LittleBacAnswers.objects.filter(round=round)
        organized_answers = {}
        for player in players:
            organized_answers[player.id] = {}
            for category in categories:
                answer = answers.filter(player=player, category=category).first()
                if answer:
                    organized_answers[player.id][category.id] = answer.answer
                else:
                    organized_answers[player.id][category.id] = ""
        all_organized_answers[round.id] = organized_answers

    # Mettre à jour les scores totaux des joueurs
    for player in players:
        player.score = total_scores[player.id]
        player.save()

    ranked_players = []
    previous_score = None
    current_rank = 0
    sorted_players = sorted(
        players, key=lambda player: total_scores[player.id], reverse=True
    )
    for position, player in enumerate(sorted_players, start=1):
        score = total_scores[player.id]
        if score != previous_score:
            current_rank = position
            previous_score = score
        ranked_players.append({
            'rank': current_rank,
            'player': player,
            'score': score,
        })

    return render(request, 'games/littlebac/results.html', {
        'game': game,
        'players': players,
        'ranked_players': ranked_players,
        'rounds': rounds,
        'categories': categories,
        'all_organized_answers': all_organized_answers,
        'scores_by_round': scores_by_round,
        'total_scores': total_scores
    })

@login_required()
def game_little_bac_start_new_round(request, game_id):
    import random
    import string

    game = get_object_or_404(LittleBacGames, id=game_id)
    if game.author != request.user:
        return redirect('bac_party_games', party_id=game_id)
    
    players = LittleBacPlayers.objects.filter(game=game)

    game.status = 'waiting'
    game.countdown_started = False
    game.countdown_start_time = None
    game.countdown_time = 0
    game.current_phase = "ready_game"
    game.save()

    players.update(is_ready=False, status='playing')

    # Sélectionne une lettre aléatoire pour le nouveau round
    alphabet = string.ascii_uppercase
    letter = random.choice(alphabet)

    # Détermine le numéro du nouveau round
    round_counter = game.rounds.count() + 1

    # Crée un nouveau round
    new_round = LittleBacRounds.objects.create(
        game=game,
        letter=letter,
        round_counter=round_counter
    )

    return redirect('bac_party_games', party_id=game_id)

# API REST DES JEUX
@login_required()
def game_players_little_bac(request, game_id):
    try:
        game = LittleBacGames.objects.get(id=game_id)
        players = LittleBacPlayers.objects.filter(game=game).select_related(
            'user'
        ).prefetch_related('user__levels')
        players_list = [
            {
                "id": player.id,
                "username": player.user.username,
                "score": player.score,
                "level": player.user.level_number,
                "level_title": player.user.level_title,
            }
            for player in players
        ]
        return JsonResponse({"game_id": game_id, "players": players_list})
    except LittleBacGames.DoesNotExist:
        return JsonResponse({"error": "Game not found"}, status=404)

@login_required()
def toggle_ready_status_little_bac(request, game_id, player_id):
    # Un joueur ne peut changer que son propre statut (player_id = id utilisateur).
    if player_id != request.user.id:
        return JsonResponse({"error": "Forbidden"}, status=403)
    try:
        game = LittleBacGames.objects.get(id=game_id)
        player = LittleBacPlayers.objects.get(game=game, user_id=player_id)

        player.is_ready = not player.is_ready
        player.save()

        # Vérifie si tous les joueurs de la partie sont prêts
        game = player.game
        all_ready = LittleBacPlayers.objects.filter(game=game, is_ready=True).count()

        return JsonResponse({"is_ready": player.is_ready, "all_ready": all_ready})
    except (LittleBacGames.DoesNotExist, LittleBacPlayers.DoesNotExist):
        return JsonResponse({"error": "Player not found"}, status=404)

def game_infos_little_bac(request, game_id):
    try:
        game = LittleBacGames.objects.get(id=game_id)

        return JsonResponse({
            "name": game.name, 
            "status": game.status,
            "created": game.created,
            "all_ready": game.players.filter(is_ready=True).count()
        })
    except LittleBacGames.DoesNotExist:
        return JsonResponse({"error": "Party not found"}, status=404)

@login_required()
def party_infos_little_bac(request, game_id):
    from django.utils.timezone import now

    try:
        game = LittleBacGames.objects.get(id=game_id)
        players = LittleBacPlayers.objects.filter(game=game).select_related(
            'user'
        ).prefetch_related('user__levels')
        players_data = [
            {
                "id": player.id,
                "username": player.user.username,
                "status": player.status,
                "score": player.score,
                "level": player.user.level_number,
                "level_title": player.user.level_title,
            }
            for player in players
        ]

        countdown_remaining = None
        if game.countdown_started and game.countdown_start_time:
            elapsed_time = (now() - game.countdown_start_time).total_seconds()
            countdown_remaining = max(0, game.countdown_time - int(elapsed_time))


        return JsonResponse({
            "game_status": game.status,
            "players": players_data,
            "countdown_time": countdown_remaining,
            "countdown_started": game.countdown_started,
            "current_phase": game.current_phase if hasattr(game, 'current_phase') else None
        })
    except LittleBacGames.DoesNotExist:
        return JsonResponse({"error": "Game not found"}, status=404)
    
@login_required()
def game_start_countdown(request, game_id):
    from django.utils.timezone import now

    # Récupère le type de décompte (ready_game ou finish_game)
    countdown_type = request.GET.get("type", "ready_game")

    if countdown_type not in ["ready_game", "finish_game"]:
        return JsonResponse({"success": False, "error": "Type de décompte invalide."}, status=400)

    try:
        game = LittleBacGames.objects.get(id=game_id)

        # Vérification des conditions pour chaque décompte
        if countdown_type == "ready_game" and not game.countdown_started and game.status == "waiting":
            game.countdown_started = True
            game.countdown_start_time = now()
            game.countdown_time = 5
            game.save()

        elif countdown_type == "finish_game" and game.status == "in_progress":
            # Vérifie si un décompte précédent n'est pas actif
            elapsed_time = (now() - game.countdown_start_time).total_seconds()
            if not game.countdown_started or elapsed_time >= game.countdown_time:
                game.countdown_started = True
                game.countdown_start_time = now()
                game.countdown_time = 60
                game.current_phase = "finish_game"
                game.save()
            else:
                return JsonResponse({"success": False, "error": "Décompte déjà en cours."}, status=400)

        else:
            return JsonResponse({"success": False, "error": "Condition de décompte non remplie."}, status=400)

        return JsonResponse({
            "success": True,
            "countdown_started": game.countdown_started,
            "countdown_time": game.countdown_time
        })
    except LittleBacGames.DoesNotExist:
        return JsonResponse({"success": False, "error": "Game not found"}, status=404)

def game_countdown_status(request, game_id):
    from django.utils.timezone import now

    game = LittleBacGames.objects.filter(id=game_id).first()
    if game is None:
        return JsonResponse({"error": "Game not found"}, status=404)

    if game.countdown_started and game.countdown_start_time:
        # Temps écoulé en secondes
        elapsed_time = (now() - game.countdown_start_time).total_seconds()
        remaining_time = max(0, game.countdown_time - int(elapsed_time))
    else:
        remaining_time = game.countdown_time

    return JsonResponse({
        "countdown_started": game.countdown_started,
        "countdown_time": remaining_time
    })

# Marge pour les horloges des navigateurs, légèrement en avance sur le serveur.
END_GAME_TOLERANCE_SECONDS = 2


def _little_bac_can_end(game):
    """La partie peut se terminer quand tous ont fini ou que le décompte final est écoulé."""
    players = LittleBacPlayers.objects.filter(game=game)
    if players.exists() and not players.exclude(status='overed').exists():
        return True
    if game.current_phase == 'finish_game' and game.countdown_started and game.countdown_start_time:
        elapsed = (now() - game.countdown_start_time).total_seconds()
        return elapsed + END_GAME_TOLERANCE_SECONDS >= game.countdown_time
    return False


@require_POST
@login_required()
def game_liitle_bac_end_game(request, game_id):
    game = LittleBacGames.objects.filter(id=game_id).first()
    if game is None:
        return JsonResponse({"error": "Game not found"}, status=404)

    # Seuls les joueurs de la partie peuvent la terminer.
    if not LittleBacPlayers.objects.filter(game=game, user=request.user).exists():
        return JsonResponse({"success": False, "error": "Vous ne jouez pas dans cette partie."}, status=403)

    # Plusieurs joueurs appellent cette route : une partie déjà finie reste un succès.
    if game.status == 'finished':
        return JsonResponse({"success": True, "message": "Game already ended."})

    if game.status != 'in_progress' or not _little_bac_can_end(game):
        return JsonResponse({"success": False, "error": "La partie n'est pas encore terminée."}, status=400)

    game.status = 'finished'
    game.save(update_fields=['status', 'updated'])
    LittleBacPlayers.objects.filter(game=game).update(status='overed')

    return JsonResponse({"success": True, "message": "Game ended successfully."})

# --- Jeu mystère -----------------------------------------------------------

from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import mystery
from .models import MysteryAttempt, MysteryGame


def mystery_home(request):
    game = mystery.today_game()
    clues = list(game.clues.all()) if game else []
    attempt = None
    if game and request.user.is_authenticated:
        attempt = MysteryAttempt.objects.filter(user=request.user, game=game).first()

    is_author = bool(game and mystery.is_author(request.user, game))
    revealed = attempt.clues_revealed if attempt else 1
    show_all = bool(attempt and attempt.is_over) or is_author
    visible_clues = clues if show_all else clues[:revealed]
    max_xp, max_gold = mystery.rewards_for(1, len(clues))
    next_xp, next_gold = mystery.rewards_for(revealed, len(clues))

    return render(request, 'games/mystery/home.html', {
        'game': game,
        'attempt': attempt,
        'is_author': is_author,
        'clues': visible_clues,
        'clues_total': len(clues),
        'clues_left': max(0, len(clues) - revealed),
        'locked_numbers': [] if show_all else list(range(revealed + 1, len(clues) + 1)),
        'max_xp': max_xp,
        'max_gold': max_gold,
        'next_xp': next_xp,
        'next_gold': next_gold,
        'streak': mystery.streak(request.user) if request.user.is_authenticated else 0,
        'leaderboard': mystery.leaderboard(game) if game else [],
        'yesterday': mystery.past_games().first(),
        'page_title': f"Le jeu mystère - {settings.SITE_NAME}",
        'page_heading': "Le jeu mystère",
        'page_description': (
            "Chaque jour, un jeu rétro à deviner à partir d'indices progressifs. "
            "Moins d'indices, plus de récompenses !"
        ),
    })


def _back_to_game():
    """Retour à la partie, directement sur le bloc de jeu plutôt qu'en haut de page."""
    return redirect(reverse('mystery_home') + '#partie')


def _playable_game_or_redirect(request):
    game = mystery.today_game()
    if game is None or not game.clues.exists():
        messages.error(request, "Aucun jeu mystère n'est proposé aujourd'hui.")
        return None
    if mystery.is_author(request.user, game):
        messages.info(request, "C'est toi qui as proposé ce jeu mystère : tu ne peux pas y jouer.")
        return None
    return game


@login_required()
@require_POST
def mystery_guess(request):
    game = _playable_game_or_redirect(request)
    if game:
        attempt, correct = mystery.guess(request.user, game, request.POST.get('guess', ''))
        if correct:
            messages.success(
                request,
                f"Bravo ! C'était bien {game.title}. "
                f"+{attempt.xp_earned} XP et +{attempt.gold_earned} pièces d'or."
            )
        elif attempt.status == MysteryAttempt.STATUS_LOST:
            messages.error(request, f"Perdu… Il fallait trouver {game.title}.")
    return _back_to_game()


@login_required()
@require_POST
def mystery_reveal(request):
    game = _playable_game_or_redirect(request)
    if game:
        mystery.reveal_next_clue(request.user, game)
    return _back_to_game()


@login_required()
@require_POST
def mystery_give_up(request):
    game = _playable_game_or_redirect(request)
    if game:
        mystery.give_up(request.user, game)
        messages.info(request, f"La réponse était {game.title}.")
    return _back_to_game()


def mystery_archives(request):
    return render(request, 'games/mystery/archives.html', {
        'games': mystery.past_games().prefetch_related('clues')[:60],
        'page_title': f"Archives du jeu mystère - {settings.SITE_NAME}",
        'page_heading': "Archives du jeu mystère",
        'page_description': "Les jeux mystères des jours précédents et leurs indices.",
    })


def _proposal_form(request, game, action):
    if request.method == 'POST':
        errors, clues = mystery.apply_form(game, request.POST, request.FILES)
        if not errors:
            game.status = MysteryGame.STATUS_PENDING
            game.rejection_reason = ''
            game.publish_date = None
            game.author = request.user
            game.save()
            mystery.save_clues(game, clues)
            messages.success(
                request,
                f"Merci ! Ton jeu mystère « {game.title} » est envoyé à l'équipe. "
                "Tu recevras un message de RetroBot dès qu'il sera relu."
            )
            return redirect('mystery_my_proposals')
        for error in errors:
            messages.error(request, error)
    return render(request, 'games/mystery/propose.html', {
        'game': game,
        'action': action,
        'slots': _mystery_slots(game, request.POST if request.method == 'POST' else None),
        'min_clues': mystery.MIN_CLUES,
        'page_title': f"Proposer un jeu mystère - {settings.SITE_NAME}",
        'page_heading': "Proposer un jeu mystère",
        'page_description': "Propose un jeu rétro à faire deviner à la communauté.",
    })


def _mystery_slots(game, posted=None):
    """Lignes d'indices du formulaire, préremplies avec la saisie ou l'existant."""
    clues = {c.order: c for c in game.clues.all()} if game.pk else {}
    slots = []
    for slot in range(1, mystery.CLUE_SLOTS + 1):
        clue = clues.get(slot)
        text = posted.get(f'clue_{slot}_text', '') if posted is not None else (clue.text if clue else '')
        slots.append({'number': slot, 'text': text, 'image': clue.image if clue and clue.image else None})
    return slots


@login_required()
def mystery_propose(request):
    if not mystery.can_propose(request.user):
        messages.error(
            request,
            f"Tu as déjà {mystery.MAX_PENDING_PROPOSALS} propositions en attente. "
            "Attends que l'équipe les relise avant d'en envoyer d'autres."
        )
        return redirect('mystery_my_proposals')
    return _proposal_form(request, MysteryGame(), 'Proposer')


@login_required()
def mystery_proposal_edit(request, game_id):
    game = get_object_or_404(MysteryGame, pk=game_id, author=request.user)
    if game.status == MysteryGame.STATUS_APPROVED:
        messages.info(request, "Ce jeu mystère est déjà validé : seule l'équipe peut encore le modifier.")
        return redirect('mystery_my_proposals')
    return _proposal_form(request, game, 'Renvoyer' if game.status == MysteryGame.STATUS_REJECTED else 'Enregistrer')


@login_required()
def mystery_my_proposals(request):
    return render(request, 'games/mystery/my_proposals.html', {
        'proposals': MysteryGame.objects.filter(author=request.user).prefetch_related('clues')
                     .order_by('-created'),
        'today': timezone.localdate(),
        'reward_xp': mystery.XP_PROPOSAL_APPROVED,
        'page_title': f"Mes jeux mystères - {settings.SITE_NAME}",
        'page_heading': "Mes jeux mystères",
        'page_description': "Les jeux mystères que tu as proposés et leur statut.",
    })
