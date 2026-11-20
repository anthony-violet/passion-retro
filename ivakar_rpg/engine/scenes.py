"""Scènes à choix : conditions, tests de caractéristique et conséquences."""
from django.db import transaction
from django.utils import timezone

from ..models import CharacterQuest, Choice, Combat, Outcome
from . import RpgError
from .character import (
    add_item, add_log, change_coins, change_hp, gain_xp, lock, owned_item_ids, remove_item, stat_values, visit,
)
from .dice import get_rng
from .rules import resolve
from .world import enter_scene


def choice_lock_reason(character, choice, owned_ids):
    if choice.required_level and character.level < choice.required_level:
        return f"Niveau {choice.required_level} requis."
    if choice.required_item_id and choice.required_item_id not in owned_ids:
        return f"Il te faut : {choice.required_item.name}."
    if choice.required_coins and character.coins < choice.required_coins:
        return f"Il te faut {choice.required_coins} écus."
    if choice.required_flag and not character.has_flag(choice.required_flag):
        return "Tu ne sais pas encore comment faire."
    if choice.forbidden_flag and character.has_flag(choice.forbidden_flag):
        return "Ce n'est plus possible."
    return None


def choices_for(character):
    """Choix de la scène courante : liste de ``(choix, raison_ou_None)`` (masqués exclus)."""
    if not character.scene_id:
        return []
    owned = owned_item_ids(character)
    result = []
    for choice in (Choice.objects.filter(scene_id=character.scene_id)
                   .select_related('required_item', 'test_characteristic')):
        reason = choice_lock_reason(character, choice, owned)
        if reason and choice.hide_if_unavailable:
            continue
        result.append((choice, reason))
    return result


def choose(character, choice_id, rng=None):
    """Joue un choix de la scène courante."""
    rng = get_rng(rng)
    with transaction.atomic():
        character = lock(character)
        if character.is_ko:
            raise RpgError("Tu es inconscient.")
        if Combat.objects.filter(character=character).exists():
            raise RpgError("Tu es en plein combat !")
        choice = (Choice.objects.select_related('required_item', 'test_characteristic')
                  .filter(pk=choice_id, scene_id=character.scene_id).first())
        if choice is None or not character.scene_id:
            raise RpgError("Ce choix n'est plus possible.")
        reason = choice_lock_reason(character, choice, owned_item_ids(character))
        if reason:
            raise RpgError(reason)

        result = Outcome.RESULT_SUCCESS
        if choice.test_characteristic_id:
            value = stat_values(character).get(choice.test_characteristic.code, 0)
            test = resolve(value, choice.test_difficulty, rng)
            add_log(character, test.describe(choice.test_characteristic.name), 'good' if test.success else 'bad')
            if not test.success:
                result = Outcome.RESULT_FAILURE
        if choice.required_coins:
            change_coins(character, -choice.required_coins)

        outcome = (Outcome.objects.filter(choice=choice, result=result)
                   .select_related('give_item', 'take_item', 'start_quest', 'complete_quest',
                                   'move_to', 'combat', 'next_scene').first())
        if outcome is None:
            # Pas de conséquence écrite : la scène se termine simplement.
            enter_scene(character, None)
        else:
            apply_outcome(character, outcome, rng)
        character.save()
    return character


def apply_outcome(character, outcome, rng=None):
    """Applique une conséquence (personnage verrouillé, non sauvegardé)."""
    from .combat import start_combat
    from .wounds import context_check, inflict

    if outcome.text:
        add_log(character, outcome.text, 'story')
    if outcome.take_item_id and remove_item(character, outcome.take_item):
        add_log(character, f"Tu perds : {outcome.take_item.name}.", 'bad')
    if outcome.give_item_id:
        add_item(character, outcome.give_item)
        add_log(character, f"Tu obtiens : {outcome.give_item.name}.", 'good')
    if outcome.coins:
        change_coins(character, outcome.coins)
        if outcome.coins > 0:
            add_log(character, f"+{outcome.coins} écus.", 'good')
        else:
            add_log(character, f"{outcome.coins} écus.", 'bad')
    if outcome.set_flag and not character.has_flag(outcome.set_flag):
        character.flags = list(character.flags or []) + [outcome.set_flag]
    if outcome.start_quest_id:
        start_quest(character, outcome.start_quest)
    if outcome.complete_quest_id:
        complete_quest(character, outcome.complete_quest)
    if outcome.xp:
        add_log(character, f"+{outcome.xp} XP.", 'good')
        gain_xp(character, outcome.xp)
    if outcome.hp:
        if outcome.hp > 0:
            add_log(character, f"+{outcome.hp} PV.", 'good')
        else:
            add_log(character, f"Tu perds {-outcome.hp} PV.", 'bad')
        if change_hp(character, outcome.hp, rng):
            return  # KO : la suite de la conséquence n'a plus lieu
    if outcome.strain_wounds:
        context_check(character, rng)
    if outcome.wound:
        inflict(character, outcome.wound, outcome.wound_label)
    if outcome.move_to_id:
        visit(character, outcome.move_to)
        add_log(character, f"Tu arrives : {outcome.move_to.name}.")
    if outcome.combat_id:
        enter_scene(character, None)
        start_combat(character, outcome.combat, then_scene=outcome.next_scene)
    else:
        enter_scene(character, outcome.next_scene)


def leave_scene(character):
    """Quitte une scène sans choix disponible (fin d'histoire)."""
    with transaction.atomic():
        character = lock(character)
        if not character.scene_id:
            return character
        if any(reason is None for _, reason in choices_for(character)):
            raise RpgError("Fais d'abord un choix.")
        enter_scene(character, None)
        character.save()
    return character


def start_quest(character, quest):
    entry, created = CharacterQuest.objects.get_or_create(character=character, quest=quest)
    if created:
        add_log(character, f"Nouvelle quête : {quest.title}.", 'good')


def complete_quest(character, quest):
    entry, _ = CharacterQuest.objects.get_or_create(character=character, quest=quest)
    if entry.status == CharacterQuest.STATUS_DONE:
        return
    entry.status = CharacterQuest.STATUS_DONE
    entry.completed_at = timezone.now()
    entry.save(update_fields=['status', 'completed_at'])
    add_log(character, f"Quête accomplie : {quest.title} !", 'good')
    if quest.reward_coins:
        change_coins(character, quest.reward_coins)
        add_log(character, f"Récompense : +{quest.reward_coins} écus.", 'good')
    if quest.reward_item_id:
        add_item(character, quest.reward_item)
        add_log(character, f"Récompense : {quest.reward_item.name}.", 'good')
    if quest.reward_xp:
        add_log(character, f"Récompense : +{quest.reward_xp} XP.", 'good')
        gain_xp(character, quest.reward_xp)
