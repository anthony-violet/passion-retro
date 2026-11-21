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
- si le monstre et le héros tombent dans la même manche, le héros l'emporte de justesse et garde 1 PV ;
- les compétences du héros (``engine.skills``) s'utilisent comme une action, puis se rechargent.

Combat de groupe (PROVISOIRE) : un membre du groupe présent dans le lieu peut rejoindre le combat d'un
autre (``join``). Le combat passe alors en manches à choix secrets et simultanés, comme les duels : la
manche se résout quand chacun a choisi, ou quand un héros qui a choisi ne veut plus attendre après
``ROUND_TIMEOUT`` (les absents se mettent en Garde). Le monstre vise un seul héros par manche (toujours
visible) et gagne la moitié de ses PV de base par allié qui rejoint. Une Feinte contre un monstre occupé à
attaquer un autre héros le prend au dépourvu. Chaque survivant reçoit les récompenses complètes, comme en
solo ; un héros KO ou en fuite quitte le combat sans rien gagner.
"""
import math
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from ..models import (
    BEHAVIOR_BALANCED, BEHAVIOR_BRUTE, BEHAVIOR_CAUTIOUS, BEHAVIOR_CUNNING, Character, Combat, CombatSeat,
    InventoryItem, Item, Party,
)
from . import RpgError
from .character import add_item, add_log, change_coins, consume, ensure_free, gain_xp, lock, sheet, stat_values
from .clash import (
    ACTIONS, ATTACKS, FEINT, GUARD, POWER, SHAKEN_ALLOWED, STRIKE, Fighter, action_label, log_entry, oppose,
    resolve_action,
)
from . import skills as skill_engine
from .dice import get_rng, weighted_pick
from .notifications import notify
from .world import enter_scene

COMBAT_LOG_SIZE = 120
HERO_ACTIONS = tuple(ACTIONS)
ITEM, FLEE = 'item', 'flee'
ITEM_PREFIX = 'item:'
# Combat de groupe.
ROUND_TIMEOUT = timedelta(minutes=2)
GROUP_HP_BONUS = 0.5  # part des PV de base du monstre ajoutée par allié
BUSY = 'busy'  # action du monstre vue par un héros qu'il n'attaque pas

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


def intention(combat, character=None):
    """Ce que le héros sait de la prochaine action du monstre : ``(code, texte)`` ou ``('', '')``.

    En groupe, le héros visé est toujours connu ; l'action ne l'est qu'après un Observer réussi par ce
    héros (ou si c'est un Coup puissant).
    """
    action = combat.monster_action
    seat = _seat_of(combat, character) if character is not None else None
    insight = seat.insight if seat is not None else combat.hero_insight
    target = combat.monster_target if seat is not None else None
    if action and (insight or action == POWER):
        text = f"{combat.monster.name} {TELEGRAPHS[action]}"
        if target is not None and action in (STRIKE, POWER, FEINT):
            text += f" ({_target_label(target, character)})"
        return action, text + "."
    if target is not None:
        return '', f"{combat.monster.name} fixe {_target_label(target, character)} du regard."
    return '', ''


def _target_label(target, character):
    return "toi" if character is not None and target.pk == character.pk else target.name


def start_combat(character, monster, then_scene=None, rng=None):
    """Engage le combat (personnage verrouillé, non sauvegardé)."""
    Combat.objects.filter(character=character).delete()
    from .party import call_for_help

    Combat.objects.filter(character=character).delete()
    combat = Combat(character=character, monster=monster, monster_hp=monster.hp, monster_max_hp=monster.hp,
                    then_scene=then_scene, monster_action=next_monster_action(monster, rng=rng))
    _log(combat, _tag_monster(combat), " surgit ! ", ('note', f"({monster.get_behavior_display()})"), kind='story')
    combat.save()
    add_log(character, f"Combat contre {monster.name} !", 'bad')
    call_for_help(character, monster)
    return combat


def _combat_query(character):
    return Combat.objects.filter(Q(character=character) | Q(seats__character=character)).distinct()


def current_combat(character):
    """Combat du héros : celui qu'il a engagé ou celui où il a pris place."""
    return (_combat_query(character).select_related('monster', 'then_scene', 'monster_target', 'character')
            .first())


def is_group(combat):
    return combat.seats.exists()


def _seat_of(combat, character):
    if character is None:
        return None
    return next((seat for seat in combat.seats.all() if seat.character_id == character.pk), None)


def participants(combat):
    """Héros engagés dans le combat."""
    seats = list(combat.seats.select_related('character'))
    return [seat.character for seat in seats] if seats else [combat.character]


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


def _hero_fighter(character, action, skill=None):
    stats = sheet(character)
    return Fighter(_tag_hero(character), stat_values(character), action, armor=stats['armor'],
                   damage_bonus=stats['damage_bonus'], skill=skill)


def _monster_fighter(combat):
    monster = combat.monster
    return Fighter(_tag_monster(combat), monster.stat_values, combat.monster_action, armor=monster.armor,
                   damage_range=(monster.damage_min, monster.damage_max))


def _fighters(character, combat, hero_action, skill=None):
    return _hero_fighter(character, hero_action, skill), _monster_fighter(combat)


def _victory(character, combat, rng):
    then_scene = combat.then_scene
    _reward(character, combat.monster, rng)
    combat.delete()
    enter_scene(character, then_scene)


def _reward(character, monster, rng):
    """Récompenses complètes d'un vainqueur (personnage verrouillé, non sauvegardé)."""
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
    gain_xp(character, monster.xp)


def _resolve_round(character, combat, hero_action, rng, skill=None):
    """Joue la manche : l'action du héros contre celle du monstre, puis l'issue."""
    from .wounds import knock_out

    if not combat.monster_action:  # combat engagé avant les manches à actions
        combat.monster_action = next_monster_action(combat.monster, combat.monster_shaken, rng)
    hero, beast = _fighters(character, combat, hero_action, skill)
    log = lambda *parts, **kw: _log(combat, *parts, **kw)  # noqa: E731
    if hero_action in ACTIONS or skill:
        log(hero.tag, " lance ", ('act', hero.label), ".", kind='cast')
    log(beast.tag, " lance ", ('act', action_label(beast.action)), ".", kind='cast')
    resolve_action(log, hero, beast, rng)
    resolve_action(log, beast, hero, rng)

    combat.monster_hp = max(0, combat.monster_hp - beast.damage_taken)
    max_hp = sheet(character)['max_hp']
    character.hp = min(max_hp, max(0, character.hp - hero.damage_taken + hero.healed))
    if combat.monster_hp == 0:
        if character.hp == 0:
            character.hp = 1
            add_log(character, "Tu t'effondres… juste après ton adversaire.", 'bad')
        _victory(character, combat, rng)
        return
    log(('note', "Fin de manche : "), hero.tag, " ", ('hp', f"{character.hp}/{max_hp} PV"),
        ('note', " · "), beast.tag, " ", ('hp', f"{combat.monster_hp}/{combat.max_hp} PV"), kind='summary')
    if character.hp == 0:
        combat.save()
        knock_out(character, rng)
        return
    combat.hero_insight = hero.insight_next
    combat.monster_shaken = beast.shaken_next
    combat.skill_cooldowns = skill_engine.tick(combat.skill_cooldowns, skill)
    combat.turn += 1
    combat.monster_action = next_monster_action(combat.monster, combat.monster_shaken, rng)
    combat.save()


def act(character, action, item_id=None, rng=None):
    """Action de combat : une action de ``clash.ACTIONS``, une compétence (``skill:<slug>``), ``item`` (boire)
    ou ``flee`` (fuir)."""
    rng = get_rng(rng)
    found = current_combat(character)
    if found is not None and (found.character_id != character.pk or is_group(found)):
        choose(character, action, item_id, rng=rng)
        return character
    with transaction.atomic():
        character = lock(character)
        combat = _locked_combat(character)
        if is_group(combat):
            raise RpgError("Un allié vient de te rejoindre : choisis à nouveau ton action.")
        monster = combat.monster

        if action in HERO_ACTIONS:
            _resolve_round(character, combat, action, rng)
        elif skill_engine.is_skill(action):
            skill = skill_engine.usable(character, action, combat.skill_cooldowns)
            _resolve_round(character, combat, action, rng, skill=skill)
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


# ---------------------------------------------------------------------------
# Combat de groupe
# ---------------------------------------------------------------------------
def joinable(character):
    """Combats que le héros peut rejoindre : ceux des membres de son groupe présents dans son lieu."""
    from .party import member_ids, party_of

    ids = [pk for pk in member_ids(party_of(character)) if pk != character.pk]
    if not ids or not character.location_id:
        return []
    combats = (Combat.objects.filter(Q(character_id__in=ids) | Q(seats__character_id__in=ids),
                                     character__location_id=character.location_id)
               .exclude(character=character).exclude(seats__character=character)
               .select_related('monster', 'character').distinct())
    return [c for c in combats if len(participants(c)) < Party.MAX_SIZE]


def join(character, combat_id, now=None):
    """Le héros rejoint le combat d'un membre de son groupe, dans le même lieu."""
    from .party import member_ids, party_of

    now = now or timezone.now()
    with transaction.atomic():
        combat = (Combat.objects.select_for_update().select_related('monster', 'character')
                  .filter(pk=combat_id).first())
        if combat is None:
            raise RpgError("Ce combat est déjà terminé.")
        character = lock(character)
        ensure_free(character)
        fighters = participants(combat)
        mates = set(member_ids(party_of(character)))
        if not any(f.pk in mates for f in fighters):
            raise RpgError("Tu ne peux rejoindre que le combat d'un membre de ton groupe.")
        if combat.character.location_id != character.location_id:
            raise RpgError(f"{combat.character.name} se bat ailleurs.")
        if len(fighters) >= Party.MAX_SIZE:
            raise RpgError("Il n'y a plus de place dans cette mêlée.")
        if not combat.seats.exists():
            CombatSeat.objects.create(combat=combat, character=combat.character, insight=combat.hero_insight,
                                      cooldowns=combat.skill_cooldowns or {})
            combat.monster_target = combat.character
            combat.round_started_at = now
        CombatSeat.objects.create(combat=combat, character=character)
        bonus = math.ceil(combat.monster.hp * GROUP_HP_BONUS)
        combat.monster_max_hp = combat.max_hp + bonus
        combat.monster_hp += bonus
        _log(combat, _tag_hero(character), " rejoint la mêlée ! ", _tag_monster(combat), " redouble de rage ",
             ('note', f"(+{bonus} PV)"), ".", kind='story')
        combat.save()
        add_log(character, f"Tu rejoins le combat contre {combat.monster.name} !", 'bad')
        character.save(update_fields=['log'])
        for other in fighters:
            notify(other, 'party_combat', f"{character.name} vient t'épauler contre {combat.monster.name} !",
                   url=reverse('rpg_play'))
    return combat


def group_state(combat, character):
    """Ce que le héros voit d'un combat de groupe."""
    seats = list(combat.seats.select_related('character'))
    mine = next((s for s in seats if s.character_id == character.pk), None)
    waiting = [s.character for s in seats if not s.action]
    return {
        'seats': [{'character': s.character, 'max_hp': sheet(s.character)['max_hp'], 'chosen': bool(s.action),
                   'is_me': s.character_id == character.pk, 'is_target': s.character_id == combat.monster_target_id}
                  for s in seats],
        'my_action': mine.action if mine else '',
        'my_action_label': action_name(mine.action) if mine and mine.action else '',
        'cooldowns': mine.cooldowns if mine else {},
        'waiting': waiting,
        'can_force': bool(mine and mine.action and waiting and _timed_out(combat)),
        'chosen_count': sum(1 for s in seats if s.action),
    }


def action_name(code):
    if code.startswith(ITEM_PREFIX):
        item = Item.objects.filter(pk=code[len(ITEM_PREFIX):] or 0).first()
        return f"🧪 {item.name}" if item else "🧪 Potion"
    if code == FLEE:
        return "🏃 Fuir"
    return skill_engine.label(code)


def _timed_out(combat, now=None):
    started = combat.round_started_at or combat.started_at
    return (now or timezone.now()) - started >= ROUND_TIMEOUT


def _locked_group(character):
    found = current_combat(character)
    if found is None:
        raise RpgError("Aucun combat en cours.")
    combat = (Combat.objects.select_for_update().select_related('monster', 'then_scene', 'character')
              .filter(pk=found.pk).first())
    if combat is None:
        raise RpgError("Ce combat est déjà terminé.")
    seat = combat.seats.select_for_update().filter(character=character).first()
    if seat is None:
        raise RpgError("Tu ne prends plus part à ce combat.")
    return combat, seat


def choose(character, action, item_id=None, rng=None):
    """Combat de groupe : enregistre l'action secrète du héros ; la manche se résout quand tous ont choisi."""
    rng = get_rng(rng)
    with transaction.atomic():
        combat, seat = _locked_group(character)
        if seat.action:
            raise RpgError("Tu as déjà choisi pour cette manche.")
        if action in HERO_ACTIONS:
            code = action
        elif skill_engine.is_skill(action):
            code = skill_engine.usable(character, action, seat.cooldowns).code
        elif action == ITEM:
            if not InventoryItem.objects.filter(inventory__character=character, item_id=item_id or 0,
                                                item__kind=Item.KIND_CONSUMABLE, quantity__gt=0).exists():
                raise RpgError("Tu ne possèdes pas cet objet.")
            code = f"{ITEM_PREFIX}{item_id}"
        elif action == FLEE:
            if combat.monster.is_boss:
                raise RpgError(f"Impossible de fuir face à {combat.monster.name} !")
            code = FLEE
        else:
            raise RpgError("Action inconnue.")
        seat.action = code
        seat.save(update_fields=['action'])
        seats = list(combat.seats.select_related('character'))
        if all(s.action for s in seats):
            _resolve_group_round(combat, rng)
        else:
            for other in seats:
                if not other.action:
                    notify(other.character, 'party_combat', f"{character.name} a choisi son action.",
                           f"À toi de jouer la manche {combat.turn} contre {combat.monster.name}.",
                           reverse('rpg_play'), ref=f"cround:{combat.pk}:{combat.turn}:{other.character_id}")
    return combat


def force_round(character, rng=None, now=None):
    """Un héros qui a choisi n'attend plus les absents : ils se mettent en Garde."""
    with transaction.atomic():
        combat, seat = _locked_group(character)
        if not seat.action:
            raise RpgError("Choisis d'abord ton action.")
        if not _timed_out(combat, now):
            raise RpgError("Laisse encore un peu de temps à tes compagnons.")
        absent = combat.seats.filter(action='')
        for other in absent.select_related('character'):
            _log(combat, _tag_hero(other.character), " hésite et se met en garde.", kind='cast')
        absent.update(action=GUARD)
        _resolve_group_round(combat, get_rng(rng))
    return combat


def _resolve_group_round(combat, rng, now=None):
    """Joue la manche de groupe : actions des héros contre le monstre, puis celle du monstre contre sa cible."""
    from .wounds import knock_out

    now = now or timezone.now()
    seats = {s.character_id: s for s in combat.seats.all()}
    heroes = list(Character.objects.select_for_update().select_related('location', 'scene')
                  .filter(pk__in=seats).order_by('pk'))
    by_pk = {h.pk: h for h in heroes}
    order = [pk for pk in seats if pk in by_pk]  # ordre d'arrivée dans la mêlée
    log = lambda *parts, **kw: _log(combat, *parts, **kw)  # noqa: E731
    if not combat.monster_action:
        combat.monster_action = next_monster_action(combat.monster, combat.monster_shaken, rng)
    beast = _monster_fighter(combat)
    target_id = combat.monster_target_id if combat.monster_target_id in by_pk else order[0]

    fighters, gone = {}, set()
    for pk in order:
        hero, seat = by_pk[pk], seats[pk]
        code = seat.action
        if code.startswith(ITEM_PREFIX):
            try:
                restored = consume(hero, code[len(ITEM_PREFIX):])
            except RpgError:
                log(_tag_hero(hero), " cherche une potion… il n'en a plus.", kind='cast')
            else:
                log(_tag_hero(hero), " boit une potion : ", ('hp', f"+{restored} PV"), ".", kind='cast')
            fighter = _hero_fighter(hero, ITEM)
        elif code == FLEE:
            fighter = _hero_fighter(hero, FLEE)
            log(fighter.tag, " tente de fuir.", kind='cast')
            if oppose(log, fighter, 'dexterite', "Dextérité", beast, 'dexterite', "Dextérité", rng) > 0:
                log(fighter.tag, " s'échappe de la mêlée.")
                add_log(hero, f"Tu prends la fuite, laissant {combat.monster.name} à tes compagnons.")
                gone.add(pk)
            else:
                log(beast.tag, " barre la route à ", fighter.tag, ".")
        else:
            fighter = _hero_fighter(hero, code, skill_engine.skill_for(code))
            log(fighter.tag, " lance ", ('act', fighter.label), ".", kind='cast')
        fighters[pk] = fighter
    target = fighters.get(target_id) if target_id not in gone else None
    log(beast.tag, " lance ", ('act', action_label(beast.action)),
        *((" contre ", target.tag) if target is not None and beast.action in (STRIKE, POWER, FEINT) else ()),
        ".", kind='cast')

    monster_action = beast.action
    for pk in order:
        if pk in gone:
            continue
        # Un monstre occupé à attaquer un autre héros n'est ni en garde ni prêt à punir une Feinte.
        beast.action = monster_action if pk == target_id or monster_action not in ATTACKS else BUSY
        resolve_action(log, fighters[pk], beast, rng)
    beast.action = monster_action
    if target is not None:
        resolve_action(log, beast, target, rng)
    elif monster_action in ATTACKS:
        log(beast.tag, " frappe dans le vide.")

    combat.monster_hp = max(0, combat.monster_hp - beast.damage_taken)
    for pk in order:
        hero, fighter = by_pk[pk], fighters[pk]
        hero.hp = min(sheet(hero)['max_hp'], max(0, hero.hp - fighter.damage_taken + fighter.healed))

    if combat.monster_hp == 0:
        winners = [by_pk[pk] for pk in order if pk not in gone]
        for hero in winners:
            if hero.hp == 0:
                hero.hp = 1
                add_log(hero, "Tu t'effondres… juste après ton adversaire.", 'bad')
        owner_id, then_scene, monster = combat.character_id, combat.then_scene, combat.monster
        log(beast.tag, " s'effondre sous les coups du groupe !", kind='end')
        combat.delete()
        for hero in winners:
            _reward(hero, monster, rng)
            if hero.pk == owner_id:
                enter_scene(hero, then_scene)
            elif len(winners) > 1:
                add_log(hero, f"Victoire du groupe contre {monster.name} !", 'good')
        for hero in heroes:
            hero.save()
        for hero in winners:
            notify(hero, 'party_victory', f"Victoire contre {monster.name} !", "Le groupe l'emporte.",
                   reverse('rpg_play'), ref=f"cwin:{owner_id}:{monster.pk}:{now.timestamp():.0f}:{hero.pk}")
        return

    summary = [('note', "Fin de manche : ")]
    for pk in order:
        if pk not in gone:
            summary += [fighters[pk].tag, " ", ('hp', f"{by_pk[pk].hp}/{sheet(by_pk[pk])['max_hp']} PV"),
                        ('note', " · ")]
    log(*summary, beast.tag, " ", ('hp', f"{combat.monster_hp}/{combat.max_hp} PV"), kind='summary')

    fallen = [pk for pk in order if pk not in gone and by_pk[pk].hp == 0]
    out = gone | set(fallen)
    remaining = [pk for pk in order if pk not in out]
    for pk in fallen:
        log(fighters[pk].tag, " tombe, inconscient.", kind='hit')

    if not remaining:
        for pk in out:
            seats[pk].delete()
        combat.delete()
    else:
        for pk in out:
            seats[pk].delete()
        if combat.character_id in out:
            combat.character = by_pk[remaining[0]]
        combat.monster_shaken = beast.shaken_next
        combat.turn += 1
        combat.monster_action = next_monster_action(combat.monster, combat.monster_shaken, rng)
        combat.round_started_at = now
        if len(remaining) == 1:
            # Seul survivant : le combat redevient solo, les actions se résolvent aussitôt.
            last = seats[remaining[0]]
            combat.hero_insight = fighters[last.character_id].insight_next
            combat.skill_cooldowns = skill_engine.tick(last.cooldowns, fighters[last.character_id].skill)
            combat.monster_target = None
            last.delete()
        else:
            combat.monster_target_id = remaining[rng.randint(0, len(remaining) - 1)]
            for pk in remaining:
                seat, fighter = seats[pk], fighters[pk]
                seat.action = ''
                seat.insight = fighter.insight_next
                seat.cooldowns = skill_engine.tick(seat.cooldowns, fighter.skill)
                seat.save(update_fields=['action', 'insight', 'cooldowns'])
        combat.save()
    for pk in fallen:
        knock_out(by_pk[pk], rng)
    for hero in heroes:
        hero.save()
    for pk in remaining:
        notify(by_pk[pk], 'party_combat', f"Manche {combat.turn - 1} résolue contre {combat.monster.name}.",
               "À toi de choisir la suivante.", reverse('rpg_play'),
               ref=f"cdone:{combat.pk}:{combat.turn}:{pk}")
