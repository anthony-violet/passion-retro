"""Déplacements et exploration."""
from django.db import transaction

from ..models import LocationExit, Scene
from . import RpgError
from .character import add_log, ensure_free, lock, owned_item_ids
from .dice import get_rng, weighted_pick


def exit_lock_reason(character, exit, owned_ids):
    """Pourquoi la sortie est fermée, ou ``None`` si on peut la prendre."""
    if exit.required_level and character.level < exit.required_level:
        return exit.locked_text or f"Niveau {exit.required_level} conseillé pour s'y aventurer."
    if exit.required_item_id and exit.required_item_id not in owned_ids:
        return exit.locked_text or f"Il te faut : {exit.required_item.name}."
    if exit.required_flag and not character.has_flag(exit.required_flag):
        return exit.locked_text or "Le chemin est barré pour l'instant."
    return None


def exits_for(character):
    """Liste de ``(sortie, raison_du_blocage_ou_None)`` du lieu courant."""
    if not character.location_id:
        return []
    owned = owned_item_ids(character)
    exits = (LocationExit.objects.filter(from_location_id=character.location_id)
             .select_related('to_location', 'required_item'))
    return [(exit, exit_lock_reason(character, exit, owned)) for exit in exits]


def move(character, exit_id, rng=None):
    """Voyage vers un lieu voisin.

    PROVISOIRE : le temps passe en voyageant. Tous les ``TIME_CHECK_EVERY`` voyages,
    chaque blessure non soignée tire son risque d'aggravation lié au temps
    (seuil = Mental × coefficient).
    """
    from .wounds import TIME_CHECK_EVERY, time_check

    with transaction.atomic():
        character = lock(character)
        ensure_free(character)
        exit = (LocationExit.objects.select_related('to_location', 'required_item')
                .filter(pk=exit_id, from_location_id=character.location_id).first())
        if exit is None:
            raise RpgError("Ce chemin ne part pas d'ici.")
        reason = exit_lock_reason(character, exit, owned_item_ids(character))
        if reason:
            raise RpgError(reason)
        character.location = exit.to_location
        add_log(character, f"Tu arrives : {exit.to_location.name}.")
        character.travel_count += 1
        if character.travel_count % TIME_CHECK_EVERY == 0:
            time_check(character, rng)
        character.save()
    return character


def scene_is_eligible(character, scene):
    if scene.min_level and character.level < scene.min_level:
        return False
    if scene.required_flag and not character.has_flag(scene.required_flag):
        return False
    if scene.forbidden_flag and character.has_flag(scene.forbidden_flag):
        return False
    if scene.once and character.has_flag(scene.seen_flag):
        return False
    return True


def enter_scene(character, scene):
    """Place le héros dans ``scene`` (personnage verrouillé, non sauvegardé)."""
    character.scene = scene
    if scene is not None and scene.once and not character.has_flag(scene.seen_flag):
        character.flags = list(character.flags or []) + [scene.seen_flag]


def explore(character, rng=None):
    """Fouille le lieu : une scène, une rencontre ou rien du tout."""
    from .combat import start_combat

    rng = get_rng(rng)
    with transaction.atomic():
        character = lock(character)
        ensure_free(character)
        location = character.location
        if location is None:
            raise RpgError("Tu es perdu dans le néant…")

        entries = [(location.calm_weight, ('calm', None))]
        scenes = Scene.objects.filter(location=location, explore_weight__gt=0)
        entries += [(scene.explore_weight, ('scene', scene))
                    for scene in scenes if scene_is_eligible(character, scene)]
        if not location.is_safe:
            entries += [(encounter.weight, ('monster', encounter.monster))
                        for encounter in location.encounters.select_related('monster')]

        kind, value = weighted_pick(entries, rng) or ('calm', None)
        if kind == 'scene':
            enter_scene(character, value)
        elif kind == 'monster':
            start_combat(character, value)
        else:
            add_log(character, "Tu fouilles les environs… rien à signaler.")
        character.save()
    return character
