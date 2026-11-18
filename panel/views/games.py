from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from games.models import LittleBacCategories, LittleBacGames


@staff_required
def games_overview(request):
    categories = LittleBacCategories.objects.all()
    recent_games = LittleBacGames.objects.select_related('author').order_by('-created')[:20]
    return render(request, 'panel/games/overview.html', {'categories': categories, 'recent_games': recent_games})


@staff_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            LittleBacCategories.objects.create(name=name, description=description)
            messages.success(request, "Catégorie créée.")
        return redirect('panel_games')
    return render(request, 'panel/games/category_form.html', {'action': 'Créer'})


@staff_required
def category_edit(request, category_id):
    category = get_object_or_404(LittleBacCategories, pk=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name', category.name).strip()
        category.description = request.POST.get('description', '').strip()
        category.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect('panel_games')
    return render(request, 'panel/games/category_form.html', {'action': 'Modifier', 'category': category})


@staff_required
def category_delete(request, category_id):
    category = get_object_or_404(LittleBacCategories, pk=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Catégorie supprimée.")
    return redirect('panel_games')


# --- Jeu mystère -----------------------------------------------------------

from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from games import mystery
from games.models import MysteryGame


@staff_required
def mystery_list(request):
    games = MysteryGame.objects.select_related('author').annotate(
        nb_clues=Count('clues', distinct=True),
        nb_players=Count('attempts', distinct=True),
        nb_winners=Count('attempts', filter=Q(attempts__status='won'), distinct=True),
    )
    return render(request, 'panel/games/mystery/list.html', {
        'pending': games.filter(status=MysteryGame.STATUS_PENDING).order_by('created'),
        'games': games.filter(status=MysteryGame.STATUS_APPROVED).order_by('-publish_date', '-id'),
        'rejected': games.filter(status=MysteryGame.STATUS_REJECTED).order_by('-updated')[:20],
        'missing_days': mystery.week_ahead_missing(),
        'today': timezone.localdate(),
    })


def _save_mystery(request, game):
    errors, clues = mystery.apply_form(game, request.POST, request.FILES)
    raw_date = request.POST.get('publish_date', '').strip()
    publish_date = None
    if raw_date:
        try:
            publish_date = date.fromisoformat(raw_date)
        except ValueError:
            errors.append("Date de publication invalide.")
    if publish_date and game.status != MysteryGame.STATUS_APPROVED:
        errors.append("Valide d'abord la proposition avant de la programmer.")
    for error in errors:
        messages.error(request, error)
    if errors:
        return False

    game.publish_date = publish_date
    if game.author_id is None:
        game.author = request.user
    try:
        with transaction.atomic():
            game.save()
            mystery.save_clues(game, clues)
    except IntegrityError:
        messages.error(request, "Un autre jeu mystère est déjà programmé ce jour-là.")
        return False
    return True


def _clue_slots(game):
    clues = list(game.clues.all()) if game and game.pk else []
    return [(slot, clues[slot - 1] if slot <= len(clues) else None)
            for slot in range(1, mystery.CLUE_SLOTS + 1)]


@staff_required
def mystery_create(request):
    game = MysteryGame()
    if request.method == 'POST' and _save_mystery(request, game):
        messages.success(request, f"Jeu mystère « {game.title} » créé.")
        return redirect('panel_games_mystery')
    return render(request, 'panel/games/mystery/form.html', {
        'action': 'Créer', 'game': game, 'slots': _clue_slots(game),
        'initial_date': request.GET.get('date', ''),
    })


@staff_required
def mystery_edit(request, game_id):
    game = get_object_or_404(MysteryGame.objects.select_related('author'), pk=game_id)
    if request.method == 'POST' and _save_mystery(request, game):
        messages.success(request, f"Jeu mystère « {game.title} » mis à jour.")
        if game.is_pending:
            # On reste sur la proposition pour pouvoir la valider juste après.
            return redirect('panel_games_mystery_edit', game_id=game.pk)
        return redirect('panel_games_mystery')
    return render(request, 'panel/games/mystery/form.html', {
        'action': 'Modifier', 'game': game, 'slots': _clue_slots(game),
    })


@staff_required
def mystery_review(request, game_id):
    game = get_object_or_404(MysteryGame.objects.select_related('author'), pk=game_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            mystery.approve(game, request.user)
            messages.success(request, f"Proposition « {game.title} » validée. Pense à la programmer !")
            return redirect('panel_games_mystery_edit', game_id=game.pk)
        if action == 'reject':
            mystery.reject(game, request.user, request.POST.get('rejection_reason', '').strip())
            messages.success(request, f"Proposition « {game.title} » refusée.")
    return redirect('panel_games_mystery')


@staff_required
def mystery_delete(request, game_id):
    game = get_object_or_404(MysteryGame, pk=game_id)
    if request.method == 'POST':
        title = game.title
        game.delete()
        messages.success(request, f"Jeu mystère « {title} » supprimé.")
    return redirect('panel_games_mystery')
