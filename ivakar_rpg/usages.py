"""« Utilisé dans » : où un élément du contenu est référencé, avec un lien vers chaque endroit (panel)."""
from django.urls import reverse

from .models import (
    Choice, Item, Location, LocationEncounter, LocationExit, Monster, MonsterLoot, Npc, NpcDialogue, Outcome, Quest,
    Scene, WorldEvent,
)


def _choice_url(choice):
    return reverse('panel_ivakar_choice_edit', args=[choice.pk])


def _outcome(outcome, what):
    choice = outcome.choice
    case = "réussite" if outcome.result == Outcome.RESULT_SUCCESS else "échec"
    return (f"{what} — « {choice.scene.title} › {choice.label} »{_tags(choice)} ({case})", _choice_url(choice))


def _tags(obj):
    return f" [{obj.tags}]" if getattr(obj, 'tags', '') else ''


def _edit(section, obj):
    return reverse('panel_ivakar_edit', args=[section, obj.pk])


def usages(obj):
    """Liste de ``(texte, url)`` décrivant où ``obj`` est utilisé."""
    found = []
    outcomes = Outcome.objects.select_related('choice__scene')
    if isinstance(obj, Item):
        found += [_outcome(o, "Donné") for o in outcomes.filter(give_item=obj)]
        found += [_outcome(o, "Retiré") for o in outcomes.filter(take_item=obj)]
        found += [(f"Exigé par le choix « {c.scene.title} › {c.label} »", _choice_url(c))
                  for c in Choice.objects.filter(required_item=obj).select_related('scene')]
        found += [(f"Exigé par le chemin {e.from_location.name} → {e.to_location.name}",
                   _edit('lieux', e.from_location))
                  for e in LocationExit.objects.filter(required_item=obj).select_related('from_location', 'to_location')]
        found += [(f"Butin de {loot.monster.name} ({loot.chance} %)", _edit('monstres', loot.monster))
                  for loot in MonsterLoot.objects.filter(item=obj).select_related('monster')]
        found += [(f"Récompense de la quête « {q.title} »", _edit('quetes', q)) for q in Quest.objects.filter(reward_item=obj)]
        found += [(f"Vendu chez le marchand de {loc.name}", _edit('lieux', loc)) for loc in obj.sold_at.all()]
        found += [(f"Récompense de l'événement « {e.name} »", _edit('evenements', e))
                  for e in WorldEvent.objects.filter(top_reward_item=obj)]
    elif isinstance(obj, Monster):
        found += [(f"Rencontré à {e.location.name} (poids {e.weight})", _edit('lieux', e.location))
                  for e in LocationEncounter.objects.filter(monster=obj).select_related('location')]
        found += [_outcome(o, "Combat") for o in outcomes.filter(combat=obj)]
        found += [(f"Créature de l'événement « {e.name} »", _edit('evenements', e))
                  for e in WorldEvent.objects.filter(monster=obj)]
    elif isinstance(obj, Quest):
        found += [_outcome(o, "Démarrée") for o in outcomes.filter(start_quest=obj)]
        found += [_outcome(o, "Terminée") for o in outcomes.filter(complete_quest=obj)]
    elif isinstance(obj, Npc):
        found += [(f"Dialogue « {d.scene.title} »{_tags(d)}", _edit('scenes', d.scene))
                  for d in NpcDialogue.objects.filter(npc=obj).select_related('scene')]
        found += [(f"Interlocuteur de la scène « {s.title} »", _edit('scenes', s))
                  for s in Scene.objects.filter(npc=obj).exclude(npc_entries__npc=obj)]
    elif isinstance(obj, Scene):
        found += [_outcome(o, "Mène ici") for o in outcomes.filter(next_scene=obj)]
        found += [(f"Dialogue de {d.npc.name}{_tags(d)}", _edit('pnj', d.npc))
                  for d in NpcDialogue.objects.filter(scene=obj).select_related('npc')]
        if obj.explore_weight and obj.location_id:
            found.append((f"Découverte en explorant {obj.location.name} (poids {obj.explore_weight})",
                          _edit('lieux', obj.location)))
    elif isinstance(obj, Location):
        found += [(f"Chemin depuis {e.from_location.name}", _edit('lieux', e.from_location))
                  for e in LocationExit.objects.filter(to_location=obj).select_related('from_location')]
        found += [_outcome(o, "Y emmène") for o in outcomes.filter(move_to=obj)]
        found += [(f"Scène « {s.title} »", _edit('scenes', s)) for s in Scene.objects.filter(location=obj)]
        found += [(f"PNJ {n.name}", _edit('pnj', n)) for n in Npc.objects.filter(locations=obj)]
        found += [(f"Événement « {e.name} »", _edit('evenements', e)) for e in WorldEvent.objects.filter(location=obj)]
    return found
