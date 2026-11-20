"""Combats contre les monstres : des manches à actions, comme les duels, face à un monstre qui a ses
propres caractéristiques et dont on peut lire les intentions.

Validé : chaque jet est 2D6 + ⌊caractéristique ÷ 3⌋ ; 0 PV mène au KO (et non à la mort).

PROVISOIRE (le combat n'est pas encore défini par les règles, voir REGLES.md) :
- chaque manche, le héros choisit une action (Frappe, Coup puissant, Garde, Feinte, Intimidation, Observer)
  pendant que le monstre joue l'action qu'il a décidée d'avance ; les deux se résolvent comme en duel
  (voir ``clash``) : oppositions, degrés de réussite, triangle Feinte > Garde > Coup puissant ;
- le monstre choisit selon son comportement (brute, prudent, rusé, équilibré) ; son Coup puissant est
  toujours annoncé (« il prend son élan »), le reste n'est visible qu'après l'avoir Observé ;
- boire une potion ou tenter de fuir prend la manche : le monstre joue son action contre un héros qui ne
  riposte pas ; la fuite est une opposition Dextérité contre Dextérité (impossible face à un boss) ;
- si le monstre et le héros tombent dans la même manche, le héros l'emporte de justesse et garde 1 PV.
"""
from django.db import transaction

from ..models import BEHAVIOR_BALANCED, BEHAVIOR_BRUTE, BEHAVIOR_CAUTIOUS, BEHAVIOR_CUNNING, Combat
from . import RpgError
from .character import add_item, add_log, change_coins, consume, gain_xp, lock, sheet, stat_values
from .clash import (
    ACTIONS, FEINT, GUARD, POWER, SHAKEN_ALLOWED, STRIKE, Fighter, action_label, log_entry, oppose,
    resolve_action,
)
from .dice import get_rng, weighted_pick
from .world import enter_scene

COMBAT_LOG_SIZE = 120
HERO_ACTIONS = tuple(ACTIONS)
ITEM, FLEE = 'item', 'flee'

# Actions favorites de chaque comportement : (Frappe, Coup puissant, Garde, Feinte).
BEHAVIOR_WEIGHTS = {
    BEHAVIOR_BRUTE: {STRIKE: 3, POWER: 4, GUARD: 1, FEINT: 0},
    BEHAVIOR_CAUTIOUS: {STRIKE: 3, POWER: 1, GUARD: 4, FEINT: 0},
    BEHAVIOR_CUNNING: {STRIKE: 3, POWER: 1, GUARD: 2, FEINT: 4},
    BEHAVIOR_BALANCED: {STRIKE: 3, POWER: 2, GUARD: 2, FEINT: 2},
}
# Ce que le joueur devine de chaque action quand elle est annoncée.
TELEGRAPHS = {
    STRIKE: "s'apprête à frapper",
    POWER: "prend son élan pour un coup puissant",
    GUARD: "se ramasse derrière sa garde",
    FEINT: "prépare une feinte",
}


def next_monster_action(monster, shaken=False, rng=None):
    weights = BEHAVIOR_WEIGHTS.get(monster.behavior, BEHAVIOR_WEIGHTS[BEHAVIOR_BALANCED])
    allowed = SHAKEN_ALLOWED if shaken else tuple(weights)
    return weighted_pick([(weights[code], code) for code in allowed], rng) or STRIKE


def intention(combat):
    """Ce que le héros sait de la prochaine action du monstre : ``(code, texte)`` ou ``('', '')``."""
    action = combat.monster_action
    if action and (combat.hero_insight or action == POWER):
        return action, f"{combat.monster.name} {TELEGRAPHS[action]}."
    return '', ''


def start_combat(character, monster, then_scene=None, rng=None):
    """Engage le combat (personnage verrouillé, non sauvegardé)."""
    Combat.objects.filter(character=character).delete()
    combat = Combat(character=character, monster=monster, monster_hp=monster.hp, then_scene=then_scene,
                    monster_action=next_monster_action(monster, rng=rng))
    _log(combat, _tag_monster(combat), " surgit ! ", ('note', f"({monster.get_behavior_display()})"), kind='story')
    combat.save()
    add_log(character, f"Combat contre {monster.name} !", 'bad')
    return combat


def current_combat(character):
    return Combat.objects.select_related('monster', 'then_scene').filter(character=character).first()


def _log(combat, *parts, kind='info', detail=''):
    combat.log = (list(combat.log or []) + [log_entry(combat.turn, parts, kind, detail)])[-COMBAT_LOG_SIZE:]


def _tag_hero(character):
    return ('c', character.name)


def _tag_monster(combat):
    return ('o', combat.monster.name)


def _locked_combat(character):
    combat = (Combat.objects.select_for_update().select_related('monster', 'then_scene')
              .filter(character=character).first())
    if combat is None:
        raise RpgError("Aucun combat en cours.")
    return combat


def _fighters(character, combat, hero_action):
    stats = sheet(character)
    hero = Fighter(_tag_hero(character), stat_values(character), hero_action, armor=stats['armor'],
                   damage_bonus=stats['damage_bonus'])
    monster = combat.monster
    beast = Fighter(_tag_monster(combat), monster.stat_values, combat.monster_action, armor=monster.armor,
                    damage_range=(monster.damage_min, monster.damage_max))
    return hero, beast


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


def _resolve_round(character, combat, hero_action, rng):
    """Joue la manche : l'action du héros contre celle du monstre, puis l'issue."""
    from .wounds import knock_out

    if not combat.monster_action:  # combat engagé avant les manches à actions
        combat.monster_action = next_monster_action(combat.monster, combat.monster_shaken, rng)
    hero, beast = _fighters(character, combat, hero_action)
    log = lambda *parts, **kw: _log(combat, *parts, **kw)  # noqa: E731
    if hero_action in ACTIONS:
        log(hero.tag, " lance ", ('act', action_label(hero_action)), ".", kind='cast')
    log(beast.tag, " lance ", ('act', action_label(beast.action)), ".", kind='cast')
    resolve_action(log, hero, beast, rng)
    resolve_action(log, beast, hero, rng)

    combat.monster_hp = max(0, combat.monster_hp - beast.damage_taken)
    character.hp = max(0, character.hp - hero.damage_taken)
    if combat.monster_hp == 0:
        if character.hp == 0:
            character.hp = 1
            add_log(character, "Tu t'effondres… juste après ton adversaire.", 'bad')
        _victory(character, combat, rng)
        return
    log(('note', "Fin de manche : "), hero.tag, " ", ('hp', f"{character.hp}/{sheet(character)['max_hp']} PV"),
        ('note', " · "), beast.tag, " ", ('hp', f"{combat.monster_hp}/{combat.monster.hp} PV"), kind='summary')
    if character.hp == 0:
        combat.save()
        knock_out(character, rng)
        return
    combat.hero_insight = hero.insight_next
    combat.monster_shaken = beast.shaken_next
    combat.turn += 1
    combat.monster_action = next_monster_action(combat.monster, combat.monster_shaken, rng)
    combat.save()


def act(character, action, item_id=None, rng=None):
    """Action de combat : une action de ``clash.ACTIONS``, ``item`` (boire) ou ``flee`` (fuir)."""
    rng = get_rng(rng)
    with transaction.atomic():
        character = lock(character)
        combat = _locked_combat(character)
        monster = combat.monster

        if action in HERO_ACTIONS:
            _resolve_round(character, combat, action, rng)
        elif action == ITEM:
            restored = consume(character, item_id)
            _log(combat, _tag_hero(character), " boit une potion : ", ('hp', f"+{restored} PV"), ".", kind='cast')
            _resolve_round(character, combat, ITEM, rng)
        elif action == FLEE:
            if monster.is_boss:
                raise RpgError(f"Impossible de fuir face à {monster.name} !")
            hero, beast = _fighters(character, combat, FLEE)
            log = lambda *parts, **kw: _log(combat, *parts, **kw)  # noqa: E731
            log(hero.tag, " tente de fuir.", kind='cast')
            if oppose(log, hero, 'dexterite', "Dextérité", beast, 'dexterite', "Dextérité", rng) > 0:
                combat.delete()
                add_log(character, f"Tu prends la fuite, {monster.name} ne te suit pas.")
            else:
                log(beast.tag, " te barre la route.")
                _resolve_round(character, combat, FLEE, rng)
        else:
            raise RpgError("Action inconnue.")
        character.save()
    return character
