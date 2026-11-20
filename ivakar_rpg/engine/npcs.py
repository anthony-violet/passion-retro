"""Personnages non joueurs : qui est présent dans le lieu, et ce qu'il dit quand on l'aborde.

Un PNJ n'a pas de moteur de dialogue à lui : « Parler » ouvre une scène ordinaire (choix, tests,
quêtes, objets, combats…). Ses entrées de dialogue sont essayées dans l'ordre ; la première dont les
conditions sont remplies l'emporte, ce qui fait évoluer ce qu'il dit avec l'histoire du héros.
"""
from django.db import transaction

from ..models import Npc, NpcDialogue
from . import RpgError
from .character import add_log, ensure_free, lock
from .world import enter_scene


def dialogue_for(character, npc, dialogues=None):
    """Première entrée de dialogue valable pour ce héros, ou ``None`` (le PNJ n'a rien à dire)."""
    for dialogue in dialogues if dialogues is not None else npc.dialogues.select_related('scene'):
        if dialogue.min_level and character.level < dialogue.min_level:
            continue
        if dialogue.required_flag and not character.has_flag(dialogue.required_flag):
            continue
        if dialogue.forbidden_flag and character.has_flag(dialogue.forbidden_flag):
            continue
        return dialogue
    return None


def npcs_here(character):
    """PNJ présents dans le lieu du héros : liste de ``(pnj, dialogue_ou_None)``."""
    if not character.location_id:
        return []
    npcs = list(Npc.objects.filter(is_active=True, locations=character.location_id))
    entries = {}
    for dialogue in NpcDialogue.objects.filter(npc__in=npcs).select_related('scene'):
        entries.setdefault(dialogue.npc_id, []).append(dialogue)
    return [(npc, dialogue_for(character, npc, entries.get(npc.pk, []))) for npc in npcs]


def talk(character, npc_id):
    """Aborde un PNJ du lieu : ouvre la scène de son dialogue du moment."""
    with transaction.atomic():
        character = lock(character)
        ensure_free(character)
        npc = Npc.objects.filter(pk=npc_id, is_active=True, locations=character.location_id).first()
        if npc is None:
            raise RpgError("Cette personne n'est pas ici.")
        dialogue = dialogue_for(character, npc)
        if dialogue is None:
            raise RpgError(f"{npc.name} n'a rien à te dire pour l'instant.")
        if npc.pk not in (character.npcs_met or []):
            character.npcs_met = list(character.npcs_met or []) + [npc.pk]
        add_log(character, f"Tu abordes {npc.name}.")
        enter_scene(character, dialogue.scene)
        character.save()
    return character
