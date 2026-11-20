"""Vues multijoueur d'Ivakar : taverne, échanges, duels et événements de serveur."""
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from .engine import RpgError
from .engine import duel as duel_engine
from .engine import events, notifications, social, trade as trade_engine
from .models import Character, Duel, InventoryItem, Item, Trade, WorldEvent
from .views import _hud, _meta, _run, player_view


# ---------------------------------------------------------------------------
# Taverne
# ---------------------------------------------------------------------------
@require_POST
@player_view
def tavern_say(request, character):
    if request.headers.get('x-requested-with') == 'fetch':
        # Envoi depuis la page de jeu sans rechargement : le champ garde le focus.
        try:
            social.say(character, request.POST.get('text', ''))
        except RpgError as error:
            return JsonResponse({'ok': False, 'error': str(error)}, status=400)
        return JsonResponse({'ok': True})
    return _run(request, social.say, character, request.POST.get('text', ''))


@player_view
def tavern_feed(request, character):
    """Messages postés après ``after`` et héros présents : rafraîchissement de la page de jeu."""
    try:
        after = int(request.GET.get('after') or 0)
    except ValueError:
        after = 0
    if not character.location_id:
        return JsonResponse({'messages': [], 'present': []})
    return JsonResponse({
        'messages': [{
            'id': m.id, 'name': m.character.name, 'text': m.text, 'mine': m.character_id == character.pk,
            'time': date_format(timezone.localtime(m.created_at), 'H:i'),
        } for m in social.tavern(character.location, after)],
        'present': [{'id': h.pk, 'name': h.name, 'level': h.level} for h in social.present_heroes(character)],
    })


# ---------------------------------------------------------------------------
# Échanges
# ---------------------------------------------------------------------------
def _tradeable(character):
    return (InventoryItem.objects.filter(inventory__character=character, quantity__gt=0)
            .exclude(item__kind=Item.KIND_QUEST).select_related('item'))


@player_view
def trades(request, character):
    pending = Trade.objects.filter(status=Trade.STATUS_PENDING).prefetch_related('lines__item')
    return render(request, 'rpg/trades.html', {
        **_meta("Échanges"), **_hud(character),
        'incoming': pending.filter(receiver=character).select_related('proposer'),
        'outgoing': pending.filter(proposer=character).select_related('receiver'),
        'history': Trade.objects.filter(Q(proposer=character) | Q(receiver=character))
        .exclude(status=Trade.STATUS_PENDING).select_related('proposer', 'receiver')
        .prefetch_related('lines__item')[:10],
    })


@player_view
def trade_new(request, character):
    other = Character.objects.filter(pk=request.GET.get('avec') or request.POST.get('receiver')).first()
    if other is None or other.pk == character.pk:
        messages.error(request, "Choisis un héros présent dans le même lieu que toi.")
        return redirect('rpg_play')
    if request.method == 'POST':
        offer = {key[6:]: value for key, value in request.POST.items()
                 if key.startswith('offer_') and key[6:].isdigit()}
        wanted = {key[8:]: value for key, value in request.POST.items()
                  if key.startswith('request_') and key[8:].isdigit()}
        try:
            trade_engine.propose(character, other.pk, offer=offer, request=wanted,
                                 offer_coins=request.POST.get('offer_coins'),
                                 request_coins=request.POST.get('request_coins'),
                                 message=request.POST.get('message', ''))
        except RpgError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Proposition envoyée à {other.name}.")
            return redirect('rpg_trades')
    return render(request, 'rpg/trade_new.html', {
        **_meta("Proposer un échange"), **_hud(character), 'other': other,
        'mine': _tradeable(character), 'theirs': _tradeable(other),
    })


@require_POST
@player_view
def trade_answer(request, character, trade_id):
    action = request.POST.get('action')
    handlers = {'accept': (trade_engine.accept, "Échange conclu !"),
                'decline': (trade_engine.decline, "Proposition refusée."),
                'cancel': (trade_engine.cancel, "Proposition annulée.")}
    if action not in handlers:
        raise Http404
    handler, success = handlers[action]
    return _run(request, handler, character, trade_id, success=success, to='rpg_trades')


# ---------------------------------------------------------------------------
# Duels
# ---------------------------------------------------------------------------
@player_view
def duels(request, character):
    open_duels = duel_engine.open_duels(character)
    return render(request, 'rpg/duels.html', {
        **_meta("Duels"), **_hud(character),
        'challenges': open_duels.filter(status=Duel.STATUS_PENDING, opponent=character),
        'sent': open_duels.filter(status=Duel.STATUS_PENDING, challenger=character),
        'active': open_duels.filter(status=Duel.STATUS_ACTIVE),
        'history': Duel.objects.filter(Q(challenger=character) | Q(opponent=character),
                                       status=Duel.STATUS_FINISHED)
        .select_related('challenger', 'opponent', 'winner')[:10],
    })


@require_POST
@player_view
def duel_challenge(request, character, character_id):
    try:
        duel = duel_engine.challenge(character, character_id)
    except RpgError as error:
        messages.error(request, str(error))
        return redirect('rpg_play')
    messages.success(request, f"Défi lancé à {duel.opponent.name}.")
    return redirect('rpg_duels')


@require_POST
@player_view
def duel_answer(request, character, duel_id):
    action = request.POST.get('action')
    if action == 'accept':
        try:
            duel_engine.accept(character, duel_id)
        except RpgError as error:
            messages.error(request, str(error))
            return redirect('rpg_duels')
        return redirect('rpg_duel', duel_id)
    handlers = {'decline': (duel_engine.decline, "Défi refusé."), 'cancel': (duel_engine.cancel, "Défi retiré.")}
    if action not in handlers:
        raise Http404
    handler, success = handlers[action]
    return _run(request, handler, character, duel_id, success=success, to='rpg_duels')


def _duel_for(character, duel_id):
    duel = (Duel.objects.select_related('challenger', 'opponent', 'winner')
            .filter(pk=duel_id).filter(Q(challenger=character) | Q(opponent=character)).first())
    if duel is None:
        raise Http404
    return duel


def _rounds(duel):
    """Journal regroupé par manche, de la plus récente à la plus ancienne."""
    rounds = {}
    for entry in duel.log or []:
        rounds.setdefault(entry.get('round', 0), []).append(entry)
    return sorted(rounds.items(), reverse=True)


@player_view
def duel_view(request, character, duel_id):
    duel = _duel_for(character, duel_id)
    state = duel_engine.view_state(duel, character) if duel.status == Duel.STATUS_ACTIVE else {}
    allowed = duel_engine.allowed_actions(duel, character) if duel.status == Duel.STATUS_ACTIVE else ()
    actions = [{'code': code, 'name': name, 'icon': icon, 'stat': stat, 'help': help_text,
                'allowed': code in allowed}
               for code, (name, icon, stat, help_text) in duel_engine.ACTIONS.items()]
    return render(request, 'rpg/duel.html', {
        **_meta("Duel"), **_hud(character), 'duel': duel, 'other': duel.other(character),
        'state': state, 'actions': actions,
        'action_names': {code: f"{icon} {name}" for code, (name, icon, _, _) in duel_engine.ACTIONS.items()},
        'can_claim': duel_engine.can_claim(duel, character),
        'rounds': _rounds(duel),
    })


@player_view
def duel_state(request, character, duel_id):
    """Signature de l'état visible : la page se recharge quand elle change."""
    duel = _duel_for(character, duel_id)
    state = duel_engine.view_state(duel, character) if duel.status == Duel.STATUS_ACTIVE else {}
    return JsonResponse({
        'status': duel.status, 'round': duel.round,
        'other_has_chosen': state.get('other_has_chosen', False),
        'revealed': state.get('revealed_action', ''),
    })


@require_POST
@player_view
def duel_action(request, character, duel_id):
    action = request.POST.get('action', '')
    try:
        if action == 'claim':
            duel_engine.claim_forfeit(character, duel_id)
        elif action == 'forfeit':
            duel_engine.forfeit(character, duel_id)
        else:
            duel_engine.choose(character, duel_id, action)
    except RpgError as error:
        messages.error(request, str(error))
    return redirect('rpg_duel', duel_id)


# ---------------------------------------------------------------------------
# Événements de serveur
# ---------------------------------------------------------------------------
@player_view
def world_event(request, character, event_id=None):
    if event_id:
        event = WorldEvent.objects.select_related('location', 'monster').filter(pk=event_id).first()
    else:
        event = events.current_event() or WorldEvent.objects.filter(starts_at__lte=timezone.now()).first()
    if event is None:
        return render(request, 'rpg/event.html', {**_meta("Événements"), **_hud(character), 'event': None})
    now = timezone.now()
    next_at = events.next_attack_at(event, character)
    return render(request, 'rpg/event.html', {
        **_meta(event.name), **_hud(character), 'event': event, 'status': events.status(event, now),
        'ranking': events.ranking(event), 'next_attack_at': next_at if next_at and next_at > now else None,
        'here': not event.location_id or event.location_id == character.location_id,
        'mine': event.participations.filter(character=character).first(),
        'past_events': WorldEvent.objects.filter(starts_at__lte=now).exclude(pk=event.pk)[:5],
        'log': list(reversed(character.log or []))[:6],
    })


@require_POST
@player_view
def world_event_attack(request, character, event_id):
    try:
        events.attack(character, event_id)
    except RpgError as error:
        messages.error(request, str(error))
    return redirect(reverse('rpg_event_detail', args=[event_id]))


# ---------------------------------------------------------------------------
# Notifications (popups et toasts)
# ---------------------------------------------------------------------------
@player_view
def notifications_feed(request, character):
    return JsonResponse({'notifications': notifications.deliver(character),
                         'poll': notifications.POLL_SECONDS})


@require_POST
@player_view
def notification_dismiss(request, character, notification_id):
    notifications.dismiss(character, notification_id)
    return JsonResponse({'ok': True})
