"""Arbre des scénarios pour le panel : d'où part chaque scène, où mène chaque choix, quels marqueurs relient
les morceaux de l'histoire.

Chaque scène n'est déroulée qu'une fois sur la page ; les autres mentions renvoient à elle (lien d'ancre),
et une scène qui ramène à une scène en cours de déroulé est signalée comme une boucle.
"""
from collections import defaultdict

from .models import Choice, LocationExit, Outcome, Scene


def _effects(outcome):
    """Ce que fait une conséquence, en étiquettes courtes ``(type, texte)``."""
    effects = []
    if outcome.text:
        effects.append(('text', "récit"))
    if outcome.xp:
        effects.append(('good', f"+{outcome.xp} XP"))
    if outcome.coins:
        effects.append(('good' if outcome.coins > 0 else 'bad', f"{outcome.coins:+d} écus"))
    if outcome.hp:
        effects.append(('good' if outcome.hp > 0 else 'bad', f"{outcome.hp:+d} PV"))
    if outcome.wound:
        label = f" « {outcome.wound_label} »" if outcome.wound_label else ''
        effects.append(('bad', f"blessure {outcome.get_wound_display().lower()}{label}"))
    if outcome.strain_wounds:
        effects.append(('bad', "sollicite les blessures"))
    if outcome.take_item_id:
        effects.append(('item', f"− {outcome.take_item.name}"))
    if outcome.give_item_id:
        effects.append(('item', f"+ {outcome.give_item.name}"))
    if outcome.set_flag:
        effects.append(('flag', f"⚑ {outcome.set_flag}"))
    if outcome.start_quest_id:
        effects.append(('quest', f"📖 démarre « {outcome.start_quest.title} »"))
    if outcome.complete_quest_id:
        effects.append(('quest', f"✅ termine « {outcome.complete_quest.title} »"))
    if outcome.move_to_id:
        effects.append(('move', f"→ {outcome.move_to.name}"))
    if outcome.combat_id:
        effects.append(('combat', f"⚔️ combat : {outcome.combat.name}"))
    return effects


def _conditions(obj):
    """Conditions d'une scène ou d'un choix, en étiquettes courtes."""
    conditions = []
    if getattr(obj, 'min_level', 0):
        conditions.append(f"niv. {obj.min_level}+")
    if getattr(obj, 'required_level', 0):
        conditions.append(f"niv. {obj.required_level}+")
    if getattr(obj, 'required_item_id', None):
        conditions.append(f"objet : {obj.required_item.name}")
    if getattr(obj, 'required_coins', 0):
        conditions.append(f"{obj.required_coins} écus")
    if obj.required_flag:
        conditions.append(f"⚑ {obj.required_flag}")
    if obj.forbidden_flag:
        conditions.append(f"sans ⚑ {obj.forbidden_flag}")
    return conditions


class _Builder:
    def __init__(self):
        self.scenes = {s.pk: s for s in Scene.objects.select_related('location')}
        self.choices = defaultdict(list)
        for choice in (Choice.objects.select_related('test_characteristic', 'required_item')
                       .order_by('order', 'pk')):
            self.choices[choice.scene_id].append(choice)
        self.outcomes = defaultdict(dict)
        for outcome in Outcome.objects.select_related('give_item', 'take_item', 'start_quest', 'complete_quest',
                                                      'move_to', 'combat'):
            self.outcomes[outcome.choice_id][outcome.result] = outcome
        self.shown = set()

    def scene(self, scene, path=()):
        node = {'scene': scene, 'conditions': _conditions(scene), 'state': 'full', 'choices': []}
        if scene.pk in path:
            node['state'] = 'loop'
            return node
        if scene.pk in self.shown:
            node['state'] = 'ref'
            return node
        self.shown.add(scene.pk)
        path = path + (scene.pk,)
        for choice in self.choices[scene.pk]:
            branches = []
            cases = [(Outcome.RESULT_SUCCESS, "Réussite" if choice.test_characteristic_id else "")]
            if choice.test_characteristic_id:
                cases.append((Outcome.RESULT_FAILURE, "Échec"))
            for result, label in cases:
                outcome = self.outcomes[choice.pk].get(result)
                branch = {'label': label, 'result': result, 'outcome': outcome, 'effects': [], 'next': None}
                if outcome is not None:
                    branch['effects'] = _effects(outcome)
                    if outcome.next_scene_id and outcome.next_scene_id in self.scenes:
                        branch['next'] = self.scene(self.scenes[outcome.next_scene_id], path)
                branches.append(branch)
            node['choices'].append({'choice': choice, 'conditions': _conditions(choice), 'branches': branches})
        return node


def build(location_id=None):
    """Groupes de scènes par lieu d'entrée, puis les scènes qu'aucune entrée n'atteint."""
    builder = _Builder()
    groups = defaultdict(list)
    for scene in sorted(builder.scenes.values(), key=lambda s: (-s.explore_weight, s.title)):
        if scene.explore_weight > 0 and scene.location_id:
            groups[scene.location_id].append(scene)
    locations = {s.location_id: s.location for s in builder.scenes.values() if s.location_id}
    result = []
    for loc_id in sorted(groups, key=lambda pk: (locations[pk].order, locations[pk].name)):
        if location_id and loc_id != location_id:
            continue
        result.append({'location': locations[loc_id], 'roots': [builder.scene(s) for s in groups[loc_id]]})
    orphans = [] if location_id else [
        builder.scene(s) for s in sorted(builder.scenes.values(), key=lambda s: s.title) if s.pk not in builder.shown
    ]
    return result, orphans


def flag_index():
    """Pour chaque marqueur : qui le pose, qui l'exige, qui l'interdit."""
    index = defaultdict(lambda: {'set_by': [], 'required_by': [], 'forbidden_by': []})
    for outcome in Outcome.objects.exclude(set_flag='').select_related('choice__scene'):
        index[outcome.set_flag]['set_by'].append(f"{outcome.choice.scene.title} › {outcome.choice.label}")
    for scene in Scene.objects.filter(once=True):
        index[scene.seen_flag]['set_by'].append(f"{scene.title} (scène unique, automatique)")
    for model, label in ((Scene, lambda o: f"scène « {o.title} »"),
                         (Choice, lambda o: f"choix « {o.scene.title} › {o.label} »"),
                         (LocationExit, lambda o: f"chemin {o.from_location.name} → {o.to_location.name}")):
        queryset = model.objects.all()
        if model is Choice:
            queryset = queryset.select_related('scene')
        if model is LocationExit:
            queryset = queryset.select_related('from_location', 'to_location')
        for obj in queryset:
            if obj.required_flag:
                index[obj.required_flag]['required_by'].append(label(obj))
            if getattr(obj, 'forbidden_flag', ''):
                index[obj.forbidden_flag]['forbidden_by'].append(label(obj))
    return sorted(index.items())
