"""Duels amicaux entre héros : manches à choix secrets et simultanés, attaques en opposition.

Validé : chaque jet est 2D6 + ⌊caractéristique ÷ 3⌋.

PROVISOIRE (les oppositions entre personnages ne sont pas encore définies par les règles, voir REGLES.md) :
- à chaque manche, les deux héros choisissent une action en secret ; la manche se résout quand
  les deux ont choisi ;
- une attaque est une opposition : chacun lance 2D6 + ⌊carac ÷ 3⌋, l'attaquant doit faire strictement
  plus que le défenseur ; l'écart donne le degré (1-2 : effleure, 3-5 : touche, 6+ : coup appuyé) ;
- dégâts : 1D6 + ⌊Force ÷ 3⌋ + bonus d'arme − armure (minimum 1) ; moitié si effleure, +1D6 si appuyé ;
- les PV du duel sont à part : aucune blessure, aucun KO, aucune perte.

Les six actions et ce qu'elles battent (triangle Feinte > Garde > Coup puissant) :

  Frappe         Dextérité contre Dextérité. Fiable ; contre une Garde, ne passe qu'à moitié.
  Coup puissant  Force contre Dextérité, +1D6 de dégâts. Contre une Garde : bloqué, et le gardien riposte.
  Garde          Ne fait rien seule ; amortit la Frappe, punit le Coup puissant, mais tombe dans la Feinte.
  Feinte         Intelligence contre Perception. Ouvre une Garde (ou un adversaire qui n'attaque pas) ;
                 trop lente contre une attaque : sans effet.
  Intimidation   Charisme contre Mental. Réussie, l'adversaire est ébranlé : à la manche suivante, il ne
                 peut que Frapper ou se mettre en Garde.
  Observer       Perception contre Intelligence. Réussi, à la manche suivante tu vois l'action de
                 l'adversaire dès qu'il l'a choisie.
"""
import math
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from ..models import Character, Duel
from . import RpgError
from .character import add_log, sheet, stat_values
from .dice import get_rng
from .notifications import notify
from .rules import bonus

FORFEIT_DELAY = timedelta(hours=24)
OPEN_STATUSES = (Duel.STATUS_PENDING, Duel.STATUS_ACTIVE)
LOG_SIZE = 300  # tout le duel reste lisible

STRIKE, POWER, GUARD, FEINT, INTIMIDATE, OBSERVE = 'strike', 'power', 'guard', 'feint', 'intimidate', 'observe'
ATTACKS = (STRIKE, POWER, FEINT)
SHAKEN_ALLOWED = (STRIKE, GUARD)

# code -> (nom, icône, caractéristique utilisée, aide affichée au joueur)
ACTIONS = {
    STRIKE: ("Frappe", "⚔️", "Dextérité", "Attaque fiable. Contre une Garde, ne passe qu'à moitié."),
    POWER: ("Coup puissant", "🔨", "Force", "+1D6 de dégâts. Contre une Garde : bloqué, et l'adversaire riposte."),
    GUARD: ("Garde", "🛡️", "Dextérité", "Amortit la Frappe et punit le Coup puissant… mais tombe dans la Feinte."),
    FEINT: ("Feinte", "🎭", "Intelligence", "Ouvre une Garde. Trop lente si l'adversaire attaque."),
    INTIMIDATE: ("Intimidation", "😠", "Charisme",
                 "Ébranle l'adversaire : à la manche suivante, il ne pourra que Frapper ou se garder."),
    OBSERVE: ("Observer", "👁️", "Perception",
              "À la manche suivante, tu verras l'action de l'adversaire dès qu'il l'aura choisie."),
}


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
    return {
        'my_action': getattr(duel, f'{me}_action'),
        'other_has_chosen': bool(their_action),
        # Observer réussi : l'action adverse est révélée dès qu'elle est choisie.
        'revealed_action': their_action if getattr(duel, f'{me}_insight') and their_action else '',
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
    """Ajoute une ligne au journal, découpée en segments typés pour un affichage lisible.

    Chaque segment est un texte simple ou un couple ``(type, texte)`` : ``c``/``o`` (nom du provocateur /
    du défié), ``act`` (action), ``roll`` (résultat d'un jet), ``dmg`` (PV perdus), ``hp`` (PV restants),
    ``state`` (état), ``note`` (précision secondaire). ``detail`` garde le calcul complet des dés.
    """
    segments = [list(part) if isinstance(part, tuple) else ['', part] for part in parts]
    segments = [[k, str(t)] for k, t in segments]
    entry = {'round': duel.round, 'text': ''.join(t for _, t in segments), 'parts': segments, 'kind': kind}
    if detail:
        entry['detail'] = detail
    duel.log = (list(duel.log or []) + [entry])[-LOG_SIZE:]


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
        if action not in ACTIONS:
            raise RpgError("Action inconnue.")
        if getattr(duel, f'{me}_action'):
            raise RpgError("Tu as déjà choisi pour cette manche.")
        if action not in allowed_actions(duel, character):
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


class _Fighter:
    def __init__(self, duel, name):
        self.name = name
        self.hero = getattr(duel, name)
        self.action = getattr(duel, f'{name}_action')
        self.stats = stat_values(self.hero)
        self.sheet = sheet(self.hero)
        self.damage_taken = 0
        self.shaken_next = False
        self.insight_next = False
        self.tag = ('c' if name == 'challenger' else 'o', self.hero.name)

    def roll(self, code, rng):
        dice = (rng.randint(1, 6), rng.randint(1, 6))
        value = self.stats.get(code, 0)
        return sum(dice) + bonus(value), f"({dice[0]}+{dice[1]})", value


def _oppose(attacker, a_code, a_label, defender, d_code, d_label, rng, duel):
    """Opposition : renvoie l'écart (positif si l'attaquant l'emporte, égalité = défenseur)."""
    a_total, a_dice, a_value = attacker.roll(a_code, rng)
    d_total, d_dice, d_value = defender.roll(d_code, rng)
    label = a_label if a_label == d_label else f"{a_label} contre {d_label}"
    _log(duel, ('note', f"Jet ({label}) : "), attacker.tag, " ", ('roll', a_total), " contre ", ('roll', d_total),
         " ", defender.tag, kind='roll',
         detail=f"{attacker.hero.name} : 2D6 {a_dice} + ⌊{a_label} {a_value} ÷ 3⌋ ({bonus(a_value)}) = {a_total} · "
                f"{defender.hero.name} : 2D6 {d_dice} + ⌊{d_label} {d_value} ÷ 3⌋ ({bonus(d_value)}) = {d_total}"
                f"{' · égalité : avantage au défenseur' if a_total == d_total else ''}")
    return a_total - d_total


def _damage(attacker, defender, margin, rng, heavy=False, halved=False):
    """Dégâts selon le degré de réussite. Renvoie (dégâts, qualificatif)."""
    amount = rng.randint(1, 6) + attacker.sheet['damage_bonus']
    if heavy:
        amount += rng.randint(1, 6)
    if margin >= 6:
        amount += rng.randint(1, 6)
        quality = "coup appuyé"
    elif margin >= 3:
        quality = "coup net"
    else:
        amount = math.ceil(amount / 2)
        quality = "effleure"
    if halved:
        amount = math.ceil(amount / 2)
    return max(1, amount - defender.sheet['armor']), quality


def _hit(duel, attacker, defender, margin, rng, heavy=False, halved=False, how=''):
    amount, quality = _damage(attacker, defender, margin, rng, heavy=heavy, halved=halved)
    defender.damage_taken += amount
    note = f" ({how}, {quality})" if how else f" ({quality})"
    _log(duel, defender.tag, " perd ", ('dmg', amount), " PV.", ('note', note), kind='hit')


def _resolve_action(duel, me, them, rng):
    """Effet de l'action de ``me`` sur ``them`` (connaissant l'action de ``them``)."""
    a, b = me.action, them.action
    if a == STRIKE:
        margin = _oppose(me, 'dexterite', "Dextérité", them, 'dexterite', "Dextérité", rng, duel)
        if margin > 0:
            _hit(duel, me, them, margin, rng, halved=(b == GUARD), how="garde percée à moitié" if b == GUARD else '')
        else:
            _log(duel, them.tag, " pare la Frappe." if b == GUARD else " esquive la Frappe.")
    elif a == POWER:
        if b == GUARD:
            _log(duel, them.tag, " bloque le Coup puissant et riposte !")
            margin = _oppose(them, 'dexterite', "Dextérité", me, 'dexterite', "Dextérité", rng, duel)
            if margin > 0:
                _hit(duel, them, me, margin, rng, how="riposte")
            else:
                _log(duel, me.tag, " se dégage de la riposte.")
        else:
            margin = _oppose(me, 'force', "Force", them, 'dexterite', "Dextérité", rng, duel)
            if margin > 0:
                _hit(duel, me, them, margin, rng, heavy=True, how="Coup puissant")
            else:
                _log(duel, them.tag, " esquive le Coup puissant.")
    elif a == FEINT:
        if b in (STRIKE, POWER):
            _log(duel, me.tag, " : Feinte trop lente, sans effet.")
        else:
            margin = _oppose(me, 'intelligence', "Intelligence", them, 'perception', "Perception", rng, duel)
            if margin > 0:
                _hit(duel, me, them, margin, rng, how="garde ouverte par la Feinte" if b == GUARD else "pris au dépourvu")
            else:
                _log(duel, them.tag, " ne mord pas à la Feinte.")
    elif a == INTIMIDATE:
        margin = _oppose(me, 'charisme', "Charisme", them, 'mental', "Mental", rng, duel)
        if margin > 0:
            them.shaken_next = True
            _log(duel, them.tag, " est ", ('state', "ébranlé"), ".",
                 ('note', " (manche suivante : Frappe ou Garde seulement)"))
        else:
            _log(duel, them.tag, " résiste à l'Intimidation.")
    elif a == OBSERVE:
        margin = _oppose(me, 'perception', "Perception", them, 'intelligence', "Intelligence", rng, duel)
        if margin > 0:
            me.insight_next = True
            _log(duel, me.tag, " perce le jeu de ", them.tag, ".",
                 ('note', " (verra son action à la manche suivante)"))
        else:
            _log(duel, them.tag, " ne laisse rien deviner.")


def _resolve_round(duel, rng):
    fighters = {name: _Fighter(duel, name) for name in ('challenger', 'opponent')}
    c, o = fighters['challenger'], fighters['opponent']
    for f in (c, o):
        name, icon = ACTIONS[f.action][:2]
        _log(duel, f.tag, " lance ", ('act', f"{icon} {name}"), ".", kind='cast')
    _resolve_action(duel, c, o, rng)
    _resolve_action(duel, o, c, rng)

    duel.challenger_hp = max(0, duel.challenger_hp - c.damage_taken)
    duel.opponent_hp = max(0, duel.opponent_hp - o.damage_taken)
    _log(duel, ('note', "Fin de manche : "), c.tag, " ", ('hp', f"{duel.challenger_hp}/{duel.challenger_max_hp} PV"),
         ('note', " · "), o.tag, " ", ('hp', f"{duel.opponent_hp}/{duel.opponent_max_hp} PV"), kind='summary')
    for f in (c, o):
        setattr(duel, f'{f.name}_action', '')
        setattr(duel, f'{f.name}_shaken', f.shaken_next)
        setattr(duel, f'{f.name}_insight', f.insight_next)

    down = [f for f in (c, o) if getattr(duel, f'{f.name}_hp') == 0]
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
