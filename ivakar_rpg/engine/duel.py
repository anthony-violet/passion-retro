"""Duels amicaux entre héros (tour par tour, asynchrones).

Validé : le jet de chaque action est 2D6 + ⌊caractéristique ÷ 3⌋ contre un seuil 10 / 13 / 16.

PROVISOIRE (les oppositions entre personnages ne sont pas encore définies, voir REGLES.md) :
- le défié joue en premier ;
- toucher : Dextérité contre un seuil moyen (13), difficile (16) si l'adversaire est en garde ;
- dégâts : 1D6 + ⌊Force ÷ 3⌋ + bonus d'arme − armure de l'adversaire (minimum 1) ;
- les PV du duel sont à part : aucune blessure, aucun KO, aucune perte ;
- un adversaire qui ne joue pas pendant 24 h peut être déclaré forfait.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import DIFFICULTY_HARD, DIFFICULTY_MEDIUM, Character, Duel
from . import RpgError
from .character import add_log, sheet
from .dice import get_rng
from .rules import resolve

LOG_SIZE = 14
FORFEIT_DELAY = timedelta(hours=24)
OPEN_STATUSES = (Duel.STATUS_PENDING, Duel.STATUS_ACTIVE)


def open_duels(character):
    return (Duel.objects.filter(Q(challenger=character) | Q(opponent=character), status__in=OPEN_STATUSES)
            .select_related('challenger', 'opponent', 'turn'))


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
    return Duel.objects.create(challenger=challenger, opponent=opponent)


def _locked(duel_id):
    duel = Duel.objects.select_for_update().filter(pk=duel_id).first()
    if duel is None:
        raise RpgError("Ce duel n'existe plus.")
    return duel


def _log(duel, text, kind='info'):
    duel.log = (list(duel.log or []) + [{'text': text, 'kind': kind}])[-LOG_SIZE:]


def accept(opponent, duel_id):
    with transaction.atomic():
        duel = _locked(duel_id)
        if duel.opponent_id != opponent.pk or duel.status != Duel.STATUS_PENDING:
            raise RpgError("Ce défi ne t'attend pas.")
        if open_duels(opponent).filter(status=Duel.STATUS_ACTIVE).exists():
            raise RpgError("Termine d'abord ton duel en cours.")
        challenger = duel.challenger
        duel.challenger_hp = duel.challenger_max_hp = sheet(challenger)['max_hp']
        duel.opponent_hp = duel.opponent_max_hp = sheet(opponent)['max_hp']
        duel.status = Duel.STATUS_ACTIVE
        duel.turn = opponent
        duel.round = 1
        _log(duel, f"{opponent.name} relève le défi de {challenger.name} !", 'good')
        duel.save()
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
    return duel


def _hp(duel, character):
    return duel.challenger_hp if character.pk == duel.challenger_id else duel.opponent_hp


def _set_hp(duel, character, value):
    if character.pk == duel.challenger_id:
        duel.challenger_hp = value
    else:
        duel.opponent_hp = value


def _finish(duel, winner, loser, reason):
    duel.status = Duel.STATUS_FINISHED
    duel.winner = winner
    duel.turn = None
    _log(duel, reason, 'good')
    heroes = {c.pk: c for c in Character.objects.select_for_update().filter(pk__in=[winner.pk, loser.pk])}
    winner, loser = heroes[winner.pk], heroes[loser.pk]
    winner.duel_wins += 1
    loser.duel_losses += 1
    add_log(winner, f"Tu remportes ton duel contre {loser.name}.", 'good')
    add_log(loser, f"{winner.name} remporte votre duel. Belle passe d'armes !", 'info')
    winner.save(update_fields=['duel_wins', 'log'])
    loser.save(update_fields=['duel_losses', 'log'])


def act(character, duel_id, action, rng=None):
    """``attack``, ``defend`` ou ``forfeit``."""
    rng = get_rng(rng)
    with transaction.atomic():
        duel = _locked(duel_id)
        if character.pk not in (duel.challenger_id, duel.opponent_id) or duel.status != Duel.STATUS_ACTIVE:
            raise RpgError("Ce duel n'est pas en cours.")
        other = duel.other(character)
        if action == 'forfeit':
            _finish(duel, other, character, f"{character.name} s'incline. Victoire de {other.name}.")
            duel.save()
            return duel
        if duel.turn_id != character.pk:
            raise RpgError(f"C'est au tour de {other.name}.")
        if duel.guarding_id == character.pk:
            duel.guarding = None  # la garde dure jusqu'au tour suivant de celui qui l'a prise
        if action == 'defend':
            duel.guarding = character
            _log(duel, f"{character.name} se met en garde.")
        elif action == 'attack':
            mine, theirs = sheet(character), sheet(other)
            threshold = DIFFICULTY_HARD if duel.guarding_id == other.pk else DIFFICULTY_MEDIUM
            test = resolve(mine['dexterity'], threshold, rng)
            _log(duel, f"{character.name} — " + test.describe("attaque (Dextérité)"),
                 'good' if test.success else 'info')
            if test.success:
                damage = max(1, rng.randint(1, 6) + mine['damage_bonus'] - theirs['armor'])
                _set_hp(duel, other, max(0, _hp(duel, other) - damage))
                _log(duel, f"{character.name} touche {other.name} : −{damage} PV.", 'good')
                if _hp(duel, other) == 0:
                    _finish(duel, character, other, f"{other.name} pose un genou à terre. {character.name} "
                                                    "remporte le duel !")
                    duel.save()
                    return duel
        else:
            raise RpgError("Action inconnue.")
        duel.turn = other
        duel.round += 1
        duel.save()
    return duel


def claim_forfeit(character, duel_id, now=None):
    """L'adversaire n'a pas joué depuis 24 h : le héros dont c'est l'attente remporte le duel."""
    now = now or timezone.now()
    with transaction.atomic():
        duel = _locked(duel_id)
        if character.pk not in (duel.challenger_id, duel.opponent_id) or duel.status != Duel.STATUS_ACTIVE:
            raise RpgError("Ce duel n'est pas en cours.")
        other = duel.other(character)
        if duel.turn_id != other.pk or now - duel.updated_at < FORFEIT_DELAY:
            raise RpgError("Ton adversaire a encore le temps de jouer.")
        _finish(duel, character, other, f"{other.name} ne s'est pas présenté : victoire de {character.name}.")
        duel.save()
    return duel
