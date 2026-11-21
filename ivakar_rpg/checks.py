"""Contrôles de cohérence du contenu d'Ivakar, affichés dans le panel."""
from .engine.rules import CHARACTERISTICS, START_MAX, START_MIN
from .models import Choice, Location, LocationExit, Npc, NpcDialogue, Origin, Outcome, Scene


def content_problems():
    """Liste de ``(niveau, message, url_name, pk)`` ; niveau : ``danger`` bloque le jeu, ``warning`` à vérifier."""
    problems = []

    if not Location.objects.filter(is_start=True).exists():
        problems.append(('danger', "Aucun lieu de départ : impossible de créer un héros.", 'panel_ivakar_list',
                         'lieux'))

    origins = list(Origin.objects.filter(is_active=True).prefetch_related('values__characteristic'))
    if not origins:
        problems.append(('danger', "Aucune origine proposée : impossible de créer un héros.", 'panel_ivakar_list',
                         'origines'))
    for origin in origins:
        values = {row.characteristic.code: row.value for row in origin.values.all()}
        if set(values) != set(CHARACTERISTICS) or not all(START_MIN <= v <= START_MAX for v in values.values()):
            problems.append(('danger', f"L'origine « {origin.name} » n'a pas ses 7 valeurs entre {START_MIN} et "
                                       f"{START_MAX}.", 'panel_ivakar_edit', ('origines', origin.pk)))

    # Marqueurs exigés quelque part mais jamais posés par une conséquence : faute de frappe probable.
    set_flags = set(Outcome.objects.exclude(set_flag='').values_list('set_flag', flat=True))
    for model, label in ((LocationExit, "une sortie"), (Scene, "la scène"), (Choice, "un choix"),
                         (NpcDialogue, "un dialogue de PNJ")):
        for obj in model.objects.exclude(required_flag=''):
            if obj.required_flag not in set_flags:
                name = getattr(obj, 'title', None) or str(obj)
                problems.append(('warning', f"Le marqueur « {obj.required_flag} » exigé par {label} « {name} » "
                                            "n'est posé par aucune conséquence.", *_target(obj)))

    # Scènes qu'aucun chemin n'atteint.
    reached = set(Outcome.objects.exclude(next_scene=None).values_list('next_scene_id', flat=True))
    reached |= set(NpcDialogue.objects.values_list('scene_id', flat=True))
    for scene in Scene.objects.filter(explore_weight=0).exclude(pk__in=reached):
        problems.append(('warning', f"La scène « {scene.title} » n'apparaît jamais (poids d'exploration à 0, "
                                    "aucun choix ni PNJ n'y mène).", 'panel_ivakar_edit', ('scenes', scene.pk)))

    for npc in Npc.objects.filter(is_active=True).prefetch_related('locations', 'dialogues'):
        if not npc.locations.all():
            problems.append(('warning', f"Le PNJ « {npc.name} » n'est placé dans aucun lieu.", 'panel_ivakar_edit',
                             ('pnj', npc.pk)))
        if not npc.dialogues.all():
            problems.append(('warning', f"Le PNJ « {npc.name} » n'a aucun dialogue.", 'panel_ivakar_edit',
                             ('pnj', npc.pk)))
    for scene in Scene.objects.filter(explore_weight__gt=0, location=None):
        problems.append(('warning', f"La scène « {scene.title} » a un poids d'exploration mais aucun lieu.",
                         'panel_ivakar_edit', ('scenes', scene.pk)))

    for scene in Scene.objects.filter(text=''):
        problems.append(('warning', f"La scène « {scene.title} » est une ébauche : son texte est encore vide.",
                         'panel_ivakar_edit', ('scenes', scene.pk)))

    # Choix avec test mais sans conséquence d'échec : l'échec termine simplement la scène.
    for choice in Choice.objects.exclude(test_characteristic=None).select_related('scene'):
        if not choice.outcomes.filter(result=Outcome.RESULT_FAILURE).exists():
            problems.append(('warning', f"Le choix « {choice.label} » ({choice.scene.title}) a un test mais "
                                        "rien n'est prévu en cas d'échec.", 'panel_ivakar_choice_edit', choice.pk))
    return problems


def _target(obj):
    if isinstance(obj, NpcDialogue):
        return 'panel_ivakar_edit', ('pnj', obj.npc_id)
    if isinstance(obj, Scene):
        return 'panel_ivakar_edit', ('scenes', obj.pk)
    if isinstance(obj, Choice):
        return 'panel_ivakar_choice_edit', obj.pk
    return 'panel_ivakar_edit', ('lieux', obj.from_location_id)
