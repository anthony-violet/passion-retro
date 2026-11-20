"""Blessures, états physiques et mise hors de combat (règles d'Ivakar, V).

Validé : trois gravités ; aggravation possible mais non systématique ; deux risques
indépendants (contexte → Force, temps sans soins → Mental) ; seuil = caractéristique
× coefficient (×5 / ×4 / ×3) ; D10 × 10 ≤ seuil → stable, sinon aggravation ;
0 PV n'est pas la mort ; blessures et états (KO) sont distincts.

PROVISOIRE (non tranché par les règles, voir REGLES.md) : quand les risques sont
tirés, ce que devient une blessure grave qui s'aggrave, la blessure subie à 0 PV,
le réveil après un KO et les soins.
"""
from django.db import transaction

from ..models import Character, Combat, Wound
from . import RpgError
from .character import add_log, lock, max_hp, start_location, stat_values
from .dice import get_rng
from .rules import aggravation_check, resolve

SEVERITY_NAMES = dict(Wound.SEVERITY_CHOICES)

# PROVISOIRE — à 0 PV : 2D6 + ⌊Constitution ÷ 3⌋ contre un seuil moyen (13).
# Réussite → blessure modérée ; échec → blessure grave (la « blessure critique »).
KO_CRITICAL_THRESHOLD = 13
# PROVISOIRE — rythme du risque lié au temps sans soins : un tirage tous les 3 voyages.
TIME_CHECK_EVERY = 3


def inflict(character, severity, label=""):
    """Ajoute une blessure (personnage verrouillé)."""
    severity = int(severity)
    if severity not in SEVERITY_NAMES:
        return None
    wound = Wound.objects.create(character=character, severity=severity, label=label[:120])
    add_log(character, f"Blessure {SEVERITY_NAMES[severity].lower()}{f' : {label}' if label else ''}.", 'bad')
    return wound


def _check(character, stat_code, stat_name, cause, rng=None):
    """Tire le risque d'aggravation de chaque blessure avec ``stat_code``. Renvoie les blessures aggravées."""
    rng = get_rng(rng)
    value = stat_values(character).get(stat_code, 0)
    worsened = []
    for wound in Wound.objects.filter(character=character):
        result = aggravation_check(value, wound.severity, rng)
        name = SEVERITY_NAMES[wound.severity].lower()
        if result.stable:
            add_log(character, f"{cause} : ta blessure {name} tient bon ({result.roll} ≤ {stat_name} × "
                               f"coefficient = {result.threshold}).")
            continue
        if wound.severity < Wound.SEVERITY_SEVERE:
            wound.severity += 1
            wound.save(update_fields=['severity'])
            add_log(character, f"{cause} : ta blessure {name} s'aggrave et devient "
                               f"{SEVERITY_NAMES[wound.severity].lower()} ({result.roll} > {result.threshold}).",
                    'bad')
        else:
            # PROVISOIRE : au-delà de « grave », rien n'est encore défini.
            add_log(character, f"{cause} : ta blessure grave te fait terriblement souffrir "
                               f"({result.roll} > {result.threshold}).", 'bad')
        worsened.append(wound)
    return worsened


def context_check(character, rng=None):
    """Risque lié au contexte (la blessure est sollicitée) : seuil = Force × coefficient."""
    return _check(character, 'force', 'Force', "Effort", rng)


def time_check(character, rng=None):
    """Risque lié au temps sans soins : seuil = Mental × coefficient."""
    return _check(character, 'mental', 'Mental', "Le temps passe", rng)


def treat_all(character):
    """PROVISOIRE — soins (nuit à l'auberge) : chaque blessure perd un degré de gravité."""
    healed = 0
    for wound in Wound.objects.filter(character=character):
        if wound.severity <= Wound.SEVERITY_LIGHT:
            wound.delete()
        else:
            wound.severity -= 1
            wound.save(update_fields=['severity'])
        healed += 1
    if healed:
        add_log(character, "Tes blessures ont été soignées : elles s'atténuent d'un degré.", 'good')


def knock_out(character, rng=None):
    """0 PV : le héros ne meurt pas. Il tombe inconscient et risque une blessure critique."""
    Combat.objects.filter(character=character).delete()
    character.scene = None
    character.hp = 0
    character.state = Character.STATE_KO
    character.knockouts += 1
    add_log(character, "Tu t'effondres, inconscient.", 'bad')
    test = resolve(stat_values(character).get('constitution', 0), KO_CRITICAL_THRESHOLD, rng)
    add_log(character, test.describe("Constitution"), 'good' if test.success else 'bad')
    if test.success:
        inflict(character, Wound.SEVERITY_MODERATE, "coups reçus avant de perdre connaissance")
    else:
        inflict(character, Wound.SEVERITY_SEVERE, "blessure critique")


def wake_up(character):
    """PROVISOIRE — reprise de connaissance au lieu de départ, à mi-PV, recueilli par les habitants."""
    with transaction.atomic():
        character = lock(character)
        if not character.is_ko:
            raise RpgError("Tu es déjà conscient.")
        character.state = Character.STATE_OK
        character.location = start_location()
        character.hp = max(1, max_hp(character) // 2)
        add_log(character, f"Tu reprends connaissance à {character.location.name}. Quelqu'un t'a ramené.", 'good')
        character.save()
    return character
