"""Combats au tour par tour : attaquer, se défendre, utiliser un objet, fuir.

Toutes les actions du héros se résolvent avec la formule validée
(2D6 + ⌊caractéristique ÷ 3⌋ contre un seuil de 10, 13 ou 16).

PROVISOIRE (le combat n'est pas encore défini par les règles, voir REGLES.md) :
- toucher : Dextérité contre le « seuil pour le toucher » du monstre ;
- dégâts : 1D6 + ⌊Force ÷ 3⌋ + bonus de l'arme − armure du monstre (minimum 1) ;
- esquive : à chaque attaque du monstre, Dextérité contre son « seuil d'esquive » ;
  en cas d'échec, dégâts du monstre − armure du héros (minimum 1) ;
- se défendre : renonce à attaquer, le seuil d'esquive baisse d'un cran ce tour-ci ;
- fuir : Dextérité contre le « seuil pour le fuir » (impossible face à un boss).
"""
from django.db import transaction

from ..models import DIFFICULTY_EASY, DIFFICULTY_HARD, DIFFICULTY_MEDIUM, Combat
from . import RpgError
from .character import add_item, add_log, change_coins, consume, gain_xp, lock, sheet
from .dice import get_rng
from .rules import resolve
from .world import enter_scene

COMBAT_LOG_SIZE = 12
# Un cran plus facile quand le héros se met en garde.
EASIER = {DIFFICULTY_HARD: DIFFICULTY_MEDIUM, DIFFICULTY_MEDIUM: DIFFICULTY_EASY, DIFFICULTY_EASY: DIFFICULTY_EASY}


def start_combat(character, monster, then_scene=None):
    """Engage le combat (personnage verrouillé, non sauvegardé)."""
    Combat.objects.filter(character=character).delete()
    combat = Combat.objects.create(character=character, monster=monster, monster_hp=monster.hp,
                                   then_scene=then_scene)
    _log(combat, f"{monster.name} surgit !", 'bad')
    combat.save(update_fields=['log'])
    add_log(character, f"Combat contre {monster.name} !", 'bad')
    return combat


def current_combat(character):
    return Combat.objects.select_related('monster', 'then_scene').filter(character=character).first()


def _log(combat, text, kind='info'):
    entries = list(combat.log or [])
    entries.append({'text': text, 'kind': kind})
    combat.log = entries[-COMBAT_LOG_SIZE:]


def _locked_combat(character):
    combat = (Combat.objects.select_for_update().select_related('monster', 'then_scene')
              .filter(character=character).first())
    if combat is None:
        raise RpgError("Aucun combat en cours.")
    return combat


def _hero_attack(combat, stats, rng):
    monster = combat.monster
    test = resolve(stats['dexterity'], monster.hit_difficulty, rng)
    _log(combat, test.describe("Attaque (Dextérité)"), 'good' if test.success else 'info')
    if not test.success:
        _log(combat, f"{monster.name} évite ton coup.")
        return
    damage = max(1, rng.randint(1, 6) + stats['damage_bonus'] - monster.armor)
    combat.monster_hp = max(0, combat.monster_hp - damage)
    _log(combat, f"Tu touches {monster.name} : −{damage} PV.", 'good')


def _monster_attack(character, combat, stats, rng):
    """Tour du monstre : le héros tente d'esquiver. Renvoie ``True`` si le héros tombe à 0 PV."""
    monster = combat.monster
    threshold = EASIER[monster.dodge_difficulty] if combat.defending else monster.dodge_difficulty
    combat.defending = False
    test = resolve(stats['dexterity'], threshold, rng)
    _log(combat, test.describe("Esquive (Dextérité)"), 'good' if test.success else 'bad')
    if test.success:
        _log(combat, f"Tu esquives l'attaque de {monster.name}.")
        return False
    damage = max(1, rng.randint(monster.damage_min, max(monster.damage_min, monster.damage_max)) - stats['armor'])
    character.hp = max(0, character.hp - damage)
    _log(combat, f"{monster.name} te frappe : −{damage} PV.", 'bad')
    return character.hp == 0


def _victory(character, combat, rng):
    monster = combat.monster
    character.victories += 1
    add_log(character, f"Victoire contre {monster.name} ! +{monster.xp} XP.", 'good')
    coins = rng.randint(monster.coins_min, max(monster.coins_min, monster.coins_max))
    if coins:
        change_coins(character, coins)
        add_log(character, f"Tu ramasses {coins} écus.", 'good')
    for loot in monster.loot.select_related('item'):
        if rng.randint(1, 100) <= loot.chance:
            add_item(character, loot.item)
            add_log(character, f"Butin : {loot.item.name}.", 'good')
    then_scene = combat.then_scene
    combat.delete()
    gain_xp(character, monster.xp)
    enter_scene(character, then_scene)


def _finish_turn(character, combat, rng):
    """Après l'action du héros : victoire, ou riposte du monstre."""
    from .wounds import knock_out

    if combat.monster_hp == 0:
        _victory(character, combat, rng)
        return
    if _monster_attack(character, combat, sheet(character), rng):
        knock_out(character, rng)
        return
    combat.turn += 1
    combat.save()


def act(character, action, item_id=None, rng=None):
    """Action de combat : ``attack``, ``defend``, ``item`` ou ``flee``."""
    rng = get_rng(rng)
    with transaction.atomic():
        character = lock(character)
        combat = _locked_combat(character)
        stats = sheet(character)
        monster = combat.monster

        if action == 'attack':
            _hero_attack(combat, stats, rng)
            _finish_turn(character, combat, rng)
        elif action == 'defend':
            combat.defending = True
            _log(combat, "Tu te mets en garde.")
            _finish_turn(character, combat, rng)
        elif action == 'item':
            restored = consume(character, item_id)
            _log(combat, f"Tu reprends des forces : +{restored} PV.", 'good')
            _finish_turn(character, combat, rng)
        elif action == 'flee':
            if monster.is_boss:
                raise RpgError(f"Impossible de fuir face à {monster.name} !")
            test = resolve(stats['dexterity'], monster.flee_difficulty, rng)
            if test.success:
                add_log(character, test.describe("Fuite (Dextérité)"), 'good')
                combat.delete()
                add_log(character, f"Tu prends la fuite, {monster.name} ne te suit pas.")
            else:
                _log(combat, test.describe("Fuite (Dextérité)"), 'bad')
                _finish_turn(character, combat, rng)
        else:
            raise RpgError("Action inconnue.")
        character.save()
    return character
