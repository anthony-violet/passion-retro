"""Duels amicaux entre héros : manches à choix secrets et simultanés.

Les actions, les oppositions et les dégâts sont ceux de ``clash`` (voir ce module).
PROVISOIRE (voir REGLES.md) : à chaque manche, les deux héros choisissent une action en secret ; la
manche se résout quand les deux ont choisi ; les PV du duel sont à part : aucune blessure, aucun KO,
aucune perte.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from ..models import Character, Duel
from . import RpgError
from .character import add_log, sheet, stat_values
from .clash import (  # noqa: F401  (ré-exportés pour les vues et les tests)
    ACTIONS, ATTACKS, FEINT, GUARD, INTIMIDATE, OBSERVE, POWER, SHAKEN_ALLOWED, STRIKE, Fighter, log_entry,
    resolve_action,
)
from . import skills as skill_engine
from .dice import get_rng
from .notifications import notify

FORFEIT_DELAY = timedelta(hours=24)
OPEN_STATUSES = (Duel.STATUS_PENDING, Duel.STATUS_ACTIVE)
LOG_SIZE = 300  # tout le duel reste lisible


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------
def open_duels(character):
    return (Duel.objects.filter(Q(challenger=character) | Q(opponent=character), status__in=OPEN_STATUSES)
            .select_related('challenger', 'opponent'))


def waiting_for(character):
    """Duels où le héros doit agir : défi reçu, ou manche où il n'a pas encore choisi."""
    return Duel.objects.filter(
        Q(status=Duel.STATUS_PENDING, opponent=character)
        | Q(status=Duel.STATUS_ACTIVE, challenger=character, challenger_action='')
        | Q(status=Duel.STATUS_ACTIVE, opponent=character, opponent_action=''))


def side(duel, character):
    """Préfixe des champs du héros dans le duel : ``challenger`` ou ``opponent``."""
    if character.pk == duel.challenger_id:
        return 'challenger'
    if character.pk == duel.opponent_id:
        return 'opponent'
    raise RpgError("Ce duel ne te concerne pas.")


def other_side(name):
    return 'opponent' if name == 'challenger' else 'challenger'


def allowed_actions(duel, character):
    me = side(duel, character)
    return SHAKEN_ALLOWED if getattr(duel, f'{me}_shaken') else tuple(ACTIONS)


def view_state(duel, character):
    """Ce que le héros a le droit de savoir de la manche en cours."""
    me, them = side(duel, character), other_side(side(duel, character))
    their_action = getattr(duel, f'{them}_action')
    my_action = getattr(duel, f'{me}_action')
    revealed = their_action if getattr(duel, f'{me}_insight') and their_action else ''
    return {
        'my_action': my_action,
        'my_action_label': skill_engine.label(my_action) if my_action else '',
        'other_has_chosen': bool(their_action),
        # Observer réussi : l'action adverse est révélée dès qu'elle est choisie.
        'revealed_action': revealed,
        'revealed_label': skill_engine.label(revealed) if revealed else '',
        'cooldowns': getattr(duel, f'{me}_cooldowns') or {},
        'shaken': getattr(duel, f'{me}_shaken'),
        'other_shaken': getattr(duel, f'{them}_shaken'),
    }


# ---------------------------------------------------------------------------
# Défi
# ---------------------------------------------------------------------------
def challenge(challenger, opponent_id):
    opponent = Character.objects.filter(pk=opponent_id).first()
    if opponent is None or opponent.pk == challenger.pk:
        raise RpgError("Choisis un autre héros.")
    if opponent.location_id != challenger.location_id:
        raise RpgError(f"{opponent.name} n'est pas ici.")
    if challenger.is_ko or opponent.is_ko:
        raise RpgError("On ne défie pas un héros inconscient.")
    if open_duels(challenger).filter(status=Duel.STATUS_ACTIVE).exists():
        raise RpgError("Termine d'abord ton duel en cours.")
    if open_duels(challenger).filter(Q(challenger=opponent) | Q(opponent=opponent)).exists():
        raise RpgError(f"Un duel avec {opponent.name} est déjà en cours ou en attente.")
    duel = Duel.objects.create(challenger=challenger, opponent=opponent)
    notify(opponent, 'duel_challenge', f"{challenger.name} te défie en duel !",
           "Un duel amical : aucune blessure, rien à perdre.", reverse('rpg_duels'))
    return duel


def _locked(duel_id):
    duel = Duel.objects.select_for_update().select_related('challenger', 'opponent').filter(pk=duel_id).first()
    if duel is None:
        raise RpgError("Ce duel n'existe plus.")
    return duel


def _log(duel, *parts, kind='info', detail=''):
    duel.log = (list(duel.log or []) + [log_entry(duel.round, parts, kind, detail)])[-LOG_SIZE:]


def _who(duel, hero):
    """Segment du nom d'un héros, coloré selon son camp."""
    return ('c' if hero.pk == duel.challenger_id else 'o', hero.name)


def accept(opponent, duel_id):
    with transaction.atomic():
        duel = _locked(duel_id)
        if duel.opponent_id != opponent.pk or duel.status != Duel.STATUS_PENDING:
            raise RpgError("Ce défi ne t'attend pas.")
        if open_duels(opponent).filter(status=Duel.STATUS_ACTIVE).exists():
            raise RpgError("Termine d'abord ton duel en cours.")
        duel.challenger_hp = duel.challenger_max_hp = sheet(duel.challenger)['max_hp']
        duel.opponent_hp = duel.opponent_max_hp = sheet(opponent)['max_hp']
        duel.status = Duel.STATUS_ACTIVE
        duel.round = 1
        _log(duel, _who(duel, opponent), " relève le défi de ", _who(duel, duel.challenger), " !", kind='story')
        duel.save()
        notify(duel.challenger, 'duel_accepted', f"{opponent.name} relève ton défi !", "Choisis ta première action.",
               _url(duel))
    return duel


def decline(opponent, duel_id):
    return _close_pending(opponent, duel_id, 'opponent_id', Duel.STATUS_DECLINED)


def cancel(challenger, duel_id):
    return _close_pending(challenger, duel_id, 'challenger_id', Duel.STATUS_CANCELLED)


def _close_pending(character, duel_id, field, status):
    with transaction.atomic():
        duel = _locked(duel_id)
        if getattr(duel, field) != character.pk or duel.status != Duel.STATUS_PENDING:
            raise RpgError("Ce défi ne te concerne pas.")
        duel.status = status
        duel.save(update_fields=['status', 'updated_at'])
        if status == Duel.STATUS_DECLINED:
            notify(duel.challenger, 'duel_declined', f"{character.name} décline ton défi.", url=reverse('rpg_duels'))
    return duel


def _url(duel):
    return reverse('rpg_duel', args=[duel.pk])


def _notify_result(duel, recipient):
    """Prévient le héros qui n'a pas déclenché la fin du duel."""
    if duel.winner_id is None:
        title = "Ton duel se termine sur un match nul."
    elif duel.winner_id == recipient.pk:
        title = f"Victoire ! Tu remportes ton duel contre {duel.other(recipient).name}."
    else:
        title = f"{duel.other(recipient).name} remporte votre duel."
    notify(recipient, 'duel_finished', title, "Belle passe d'armes.", _url(duel))


# ---------------------------------------------------------------------------
# Manches
# ---------------------------------------------------------------------------
def choose(character, duel_id, action, rng=None):
    """Enregistre l'action secrète du héros ; résout la manche si l'adversaire a déjà choisi."""
    with transaction.atomic():
        duel = _locked(duel_id)
        if duel.status != Duel.STATUS_ACTIVE:
            raise RpgError("Ce duel n'est pas en cours.")
        me = side(duel, character)
        if getattr(duel, f'{me}_action'):
            raise RpgError("Tu as déjà choisi pour cette manche.")
        if skill_engine.is_skill(action):
            skill_engine.usable(character, action, getattr(duel, f'{me}_cooldowns'),
                                shaken=getattr(duel, f'{me}_shaken'))
        elif action not in ACTIONS:
            raise RpgError("Action inconnue.")
        elif action not in allowed_actions(duel, character):
            raise RpgError("Ébranlé, tu ne peux que Frapper ou te mettre en Garde à cette manche.")
        setattr(duel, f'{me}_action', action)
        other = getattr(duel, other_side(me))
        if duel.challenger_action and duel.opponent_action:
            played = duel.round
            _resolve_round(duel, get_rng(rng))
            if duel.status == Duel.STATUS_FINISHED:
                _notify_result(duel, other)
            else:
                notify(other, 'duel_round', f"Manche {played} résolue contre {character.name}.",
                       f"À toi de choisir pour la manche {duel.round}.", _url(duel))
        else:
            notify(other, 'duel_your_move', f"{character.name} a fait son choix.",
                   f"À toi de jouer la manche {duel.round}.", _url(duel))
        duel.save()
    return duel


def _fighter(duel, side_name):
    hero = getattr(duel, side_name)
    stats = sheet(hero)
    action = getattr(duel, f'{side_name}_action')
    fighter = Fighter(('c' if side_name == 'challenger' else 'o', hero.name), stat_values(hero),
                      action, armor=stats['armor'], damage_bonus=stats['damage_bonus'],
                      skill=skill_engine.skill_for(action))
    fighter.side, fighter.hero = side_name, hero
    return fighter


def _resolve_round(duel, rng):
    c, o = _fighter(duel, 'challenger'), _fighter(duel, 'opponent')
    log = lambda *parts, **kw: _log(duel, *parts, **kw)  # noqa: E731
    for f in (c, o):
        _log(duel, f.tag, " lance ", ('act', f.label), ".", kind='cast')
    resolve_action(log, c, o, rng)
    resolve_action(log, o, c, rng)

    duel.challenger_hp = min(duel.challenger_max_hp, max(0, duel.challenger_hp - c.damage_taken + c.healed))
    duel.opponent_hp = min(duel.opponent_max_hp, max(0, duel.opponent_hp - o.damage_taken + o.healed))
    _log(duel, ('note', "Fin de manche : "), c.tag, " ", ('hp', f"{duel.challenger_hp}/{duel.challenger_max_hp} PV"),
         ('note', " · "), o.tag, " ", ('hp', f"{duel.opponent_hp}/{duel.opponent_max_hp} PV"), kind='summary')
    for f in (c, o):
        setattr(duel, f'{f.side}_action', '')
        setattr(duel, f'{f.side}_shaken', f.shaken_next)
        setattr(duel, f'{f.side}_insight', f.insight_next)
        setattr(duel, f'{f.side}_cooldowns', skill_engine.tick(getattr(duel, f'{f.side}_cooldowns'), f.skill))

    down = [f for f in (c, o) if getattr(duel, f'{f.side}_hp') == 0]
    if len(down) == 2:
        _finish(duel, None, None, ("Les deux duellistes s'effondrent en même temps : match nul !",))
    elif down:
        loser = down[0]
        winner = o if loser is c else c
        _finish(duel, winner.hero, loser.hero, (loser.tag, " pose un genou à terre. ", winner.tag,
                                                " remporte le duel !"))
    else:
        duel.round += 1


def _finish(duel, winner, loser, reason):
    """``reason`` : segments du journal (voir ``_log``)."""
    duel.status = Duel.STATUS_FINISHED
    duel.winner = winner
    _log(duel, *reason, kind='end')
    if winner is None:
        for hero in Character.objects.select_for_update().filter(pk__in=[duel.challenger_id, duel.opponent_id]):
            add_log(hero, "Ton duel se termine sur un match nul.", 'info')
            hero.save(update_fields=['log'])
        return
    heroes = {c.pk: c for c in Character.objects.select_for_update().filter(pk__in=[winner.pk, loser.pk])}
    winner, loser = heroes[winner.pk], heroes[loser.pk]
    winner.duel_wins += 1
    loser.duel_losses += 1
    add_log(winner, f"Tu remportes ton duel contre {loser.name}.", 'good')
    add_log(loser, f"{winner.name} remporte votre duel. Belle passe d'armes !", 'info')
    winner.save(update_fields=['duel_wins', 'log'])
    loser.save(update_fields=['duel_losses', 'log'])


def forfeit(character, duel_id):
    with transaction.atomic():
        duel = _locked(duel_id)
        if duel.status != Duel.STATUS_ACTIVE:
            raise RpgError("Ce duel n'est pas en cours.")
        me = side(duel, character)
        other = getattr(duel, other_side(me))
        _finish(duel, other, character, (_who(duel, character), " s'incline. Victoire de ", _who(duel, other), "."))
        duel.save()
        _notify_result(duel, other)
    return duel


def claim_forfeit(character, duel_id, now=None):
    """Le héros a choisi, l'adversaire ne joue plus depuis 24 h : victoire par forfait."""
    now = now or timezone.now()
    with transaction.atomic():
        duel = _locked(duel_id)
        if duel.status != Duel.STATUS_ACTIVE:
            raise RpgError("Ce duel n'est pas en cours.")
        me, them = side(duel, character), other_side(side(duel, character))
        if not getattr(duel, f'{me}_action') or getattr(duel, f'{them}_action') \
                or now - duel.updated_at < FORFEIT_DELAY:
            raise RpgError("Ton adversaire a encore le temps de jouer.")
        other = getattr(duel, them)
        _finish(duel, character, other, (_who(duel, other), " ne s'est pas présenté : victoire de ",
                                         _who(duel, character), "."))
        duel.save()
        _notify_result(duel, other)
    return duel


def can_claim(duel, character, now=None):
    if duel.status != Duel.STATUS_ACTIVE:
        return False
    me, them = side(duel, character), other_side(side(duel, character))
    return (bool(getattr(duel, f'{me}_action')) and not getattr(duel, f'{them}_action')
            and (now or timezone.now()) - duel.updated_at >= FORFEIT_DELAY)
