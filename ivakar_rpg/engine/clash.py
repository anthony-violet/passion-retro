"""Affrontements à actions : ce que partagent les duels entre héros et les combats contre les monstres.

Validé : chaque jet est 2D6 + ⌊caractéristique ÷ 3⌋.

PROVISOIRE (les oppositions ne sont pas encore définies par les règles, voir REGLES.md) :
- une attaque est une opposition : chacun lance 2D6 + ⌊carac ÷ 3⌋, l'attaquant doit faire strictement
  plus que le défenseur ; l'écart donne le degré (1-2 : effleure, 3-5 : coup net, 6+ : coup appuyé) ;
- dégâts de base (héros : 1D6 + ⌊Force ÷ 3⌋ + arme ; monstre : sa fourchette) − armure, minimum 1 ;
  moitié si le coup effleure, +1D6 s'il est appuyé, +1D6 pour un Coup puissant.

Les six actions et ce qu'elles battent (triangle Feinte > Garde > Coup puissant) :

  Frappe         Dextérité contre Dextérité. Fiable ; contre une Garde, ne passe qu'à moitié.
  Coup puissant  Force contre Dextérité, +1D6 de dégâts. Contre une Garde : bloqué, et le gardien riposte.
  Garde          Ne fait rien seule ; amortit la Frappe, punit le Coup puissant, mais tombe dans la Feinte.
  Feinte         Intelligence contre Perception. Ouvre une Garde (ou un adversaire qui n'attaque pas) ;
                 trop lente contre une attaque : sans effet.
  Intimidation   Charisme contre Mental. Réussie, l'adversaire est ébranlé : à la manche suivante, il ne
                 peut que Frapper ou se mettre en Garde.
  Observer       Perception contre Intelligence. Réussi, à la manche suivante on voit l'action adverse.

Toute autre action (boire une potion, tenter de fuir) ne fait rien contre l'adversaire : elle subit
simplement son action.
"""
import math

from .rules import bonus

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
              "À la manche suivante, tu verras l'action de l'adversaire avant de choisir."),
}


def action_label(code):
    name, icon = ACTIONS[code][:2]
    return f"{icon} {name}"


class Fighter:
    """Un combattant le temps d'une manche.

    ``tag`` : segment de journal ``(camp, nom)`` ; ``stats`` : valeurs des caractéristiques par code ;
    ``damage_range`` + ``damage_bonus`` : dégâts de base ; ``armor`` : dégâts absorbés.
    """

    def __init__(self, tag, stats, action, armor=0, damage_range=(1, 6), damage_bonus=0):
        self.tag = tag
        self.stats = stats
        self.action = action
        self.armor = armor
        self.damage_range = damage_range
        self.damage_bonus = damage_bonus
        self.damage_taken = 0
        self.shaken_next = False
        self.insight_next = False

    @property
    def name(self):
        return self.tag[1]

    def roll(self, code, rng):
        dice = (rng.randint(1, 6), rng.randint(1, 6))
        value = self.stats.get(code, 0)
        return sum(dice) + bonus(value), f"({dice[0]}+{dice[1]})", value

    def base_damage(self, rng):
        low, high = self.damage_range
        return rng.randint(low, max(low, high)) + self.damage_bonus


def oppose(log, attacker, a_code, a_label, defender, d_code, d_label, rng):
    """Opposition : renvoie l'écart (positif si l'attaquant l'emporte, égalité = défenseur)."""
    a_total, a_dice, a_value = attacker.roll(a_code, rng)
    d_total, d_dice, d_value = defender.roll(d_code, rng)
    label = a_label if a_label == d_label else f"{a_label} contre {d_label}"
    log(('note', f"Jet ({label}) : "), attacker.tag, " ", ('roll', a_total), " contre ", ('roll', d_total),
        " ", defender.tag, kind='roll',
        detail=f"{attacker.name} : 2D6 {a_dice} + ⌊{a_label} {a_value} ÷ 3⌋ ({bonus(a_value)}) = {a_total} · "
               f"{defender.name} : 2D6 {d_dice} + ⌊{d_label} {d_value} ÷ 3⌋ ({bonus(d_value)}) = {d_total}"
               f"{' · égalité : avantage au défenseur' if a_total == d_total else ''}")
    return a_total - d_total


def damage(attacker, defender, margin, rng, heavy=False, halved=False):
    """Dégâts selon le degré de réussite. Renvoie (dégâts, qualificatif)."""
    amount = attacker.base_damage(rng)
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
    return max(1, amount - defender.armor), quality


def hit(log, attacker, defender, margin, rng, heavy=False, halved=False, how=''):
    amount, quality = damage(attacker, defender, margin, rng, heavy=heavy, halved=halved)
    defender.damage_taken += amount
    note = f" ({how}, {quality})" if how else f" ({quality})"
    log(defender.tag, " perd ", ('dmg', amount), " PV.", ('note', note), kind='hit')


def resolve_action(log, me, them, rng):
    """Effet de l'action de ``me`` sur ``them`` (connaissant l'action de ``them``)."""
    a, b = me.action, them.action
    if a == STRIKE:
        margin = oppose(log, me, 'dexterite', "Dextérité", them, 'dexterite', "Dextérité", rng)
        if margin > 0:
            hit(log, me, them, margin, rng, halved=(b == GUARD), how="garde percée à moitié" if b == GUARD else '')
        else:
            log(them.tag, " pare la Frappe." if b == GUARD else " esquive la Frappe.")
    elif a == POWER:
        if b == GUARD:
            log(them.tag, " bloque le Coup puissant et riposte !")
            margin = oppose(log, them, 'dexterite', "Dextérité", me, 'dexterite', "Dextérité", rng)
            if margin > 0:
                hit(log, them, me, margin, rng, how="riposte")
            else:
                log(me.tag, " se dégage de la riposte.")
        else:
            margin = oppose(log, me, 'force', "Force", them, 'dexterite', "Dextérité", rng)
            if margin > 0:
                hit(log, me, them, margin, rng, heavy=True, how="Coup puissant")
            else:
                log(them.tag, " esquive le Coup puissant.")
    elif a == FEINT:
        if b in (STRIKE, POWER):
            log(me.tag, " : Feinte trop lente, sans effet.")
        else:
            margin = oppose(log, me, 'intelligence', "Intelligence", them, 'perception', "Perception", rng)
            if margin > 0:
                hit(log, me, them, margin, rng, how="garde ouverte par la Feinte" if b == GUARD else "pris au dépourvu")
            else:
                log(them.tag, " ne mord pas à la Feinte.")
    elif a == INTIMIDATE:
        margin = oppose(log, me, 'charisme', "Charisme", them, 'mental', "Mental", rng)
        if margin > 0:
            them.shaken_next = True
            log(them.tag, " est ", ('state', "ébranlé"), ".",
                ('note', " (manche suivante : Frappe ou Garde seulement)"))
        else:
            log(them.tag, " résiste à l'Intimidation.")
    elif a == OBSERVE:
        margin = oppose(log, me, 'perception', "Perception", them, 'intelligence', "Intelligence", rng)
        if margin > 0:
            me.insight_next = True
            log(me.tag, " perce le jeu de ", them.tag, ".", ('note', " (verra son action à la manche suivante)"))
        else:
            log(them.tag, " ne laisse rien deviner.")


def log_entry(round_number, parts, kind='info', detail=''):
    """Ligne de journal découpée en segments typés (voir ``templates/rpg/partials/clash_log.html``).

    Chaque segment est un texte simple ou un couple ``(type, texte)`` : ``c``/``o`` (nom de chaque camp),
    ``act`` (action), ``roll`` (résultat d'un jet), ``dmg`` (PV perdus), ``hp`` (PV restants), ``state`` (état),
    ``note`` (précision secondaire). ``detail`` garde le calcul complet des dés.
    """
    segments = [[k, str(t)] for k, t in (part if isinstance(part, tuple) else ('', part) for part in parts)]
    entry = {'round': round_number, 'text': ''.join(t for _, t in segments), 'parts': segments, 'kind': kind}
    if detail:
        entry['detail'] = detail
    return entry


def group_rounds(log):
    """Journal regroupé par manche, de la plus récente à la plus ancienne."""
    rounds = {}
    for entry in log or []:
        rounds.setdefault(entry.get('round', 0), []).append(entry)
    return sorted(rounds.items(), key=lambda item: item[0], reverse=True)
