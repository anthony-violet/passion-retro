"""Panel — Ivakar : tout le contenu du RPG, les héros et le bureau de change."""
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ivakar_rpg import scenario_tree
from ivakar_rpg.checks import content_problems
from ivakar_rpg.engine import character as hero
from ivakar_rpg.engine.rules import CHARACTERISTICS
from ivakar_rpg.engine.events import current_event
from ivakar_rpg.engine.worldmap import map_for
from ivakar_rpg.models import (
    MAP_SIZE, Character, CharacterQuest, Choice, CoinExchange, Combat, InventoryItem, Location, LocationMessage,
    Outcome, Scene, WorldMap, Wound,
)
from panel.decorators import staff_required
from panel.ivakar_sections import SECTIONS, ChoiceForm, OutcomeForm

PER_PAGE = 30


def _section(slug):
    section = SECTIONS.get(slug)
    if section is None:
        raise Http404
    return section


def _cell(obj, path):
    """Valeur affichable d'une colonne : libellé des choix, booléen, chemin pointé ``a.b``."""
    value = obj
    for part in path.split('.'):
        display = getattr(value, f'get_{part}_display', None)
        value = display() if display else getattr(value, part, None)
        if callable(value) and not hasattr(value, 'get_queryset'):  # méthode, pas un gestionnaire de relation
            value = value()
    return value


def _nav():
    return [{'slug': slug, 'title': s['title'], 'icon': s['icon']} for slug, s in SECTIONS.items()]


def _render(request, template, context):
    return render(request, template, {'ivakar_sections': _nav(), **context})


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------
@staff_required
def overview(request):
    problems = []
    for level, message, url_name, target in content_problems():
        args = target if isinstance(target, tuple) else (target,)
        problems.append({'level': level, 'message': message, 'url': reverse(url_name, args=args)})
    counts = {slug: s['model'].objects.count() for slug, s in SECTIONS.items()}
    return _render(request, 'panel/ivakar/overview.html', {
        'is_open': getattr(settings, 'RPG_OPEN', False),
        'counts': counts,
        'heroes_count': Character.objects.count(),
        'in_combat': Combat.objects.count(),
        'ko_count': Character.objects.filter(state=Character.STATE_KO).count(),
        'exchanges': CoinExchange.objects.aggregate(gold=Sum('gold_spent'), coins=Sum('coins_received'),
                                                    n=Count('id')),
        'problems': problems,
        'top_heroes': Character.objects.select_related('user').order_by('-level', '-xp')[:5],
        'world_event': current_event(),
    })


# ---------------------------------------------------------------------------
# Arbre des scénarios
# ---------------------------------------------------------------------------
@staff_required
def scenario_tree_view(request):
    try:
        location_id = int(request.GET.get('lieu') or 0) or None
    except ValueError:
        location_id = None
    groups, orphans = scenario_tree.build(location_id)
    return _render(request, 'panel/ivakar/tree.html', {
        'section': 'arbre',
        'groups': groups,
        'orphans': orphans,
        'flags': scenario_tree.flag_index() if not location_id else [],
        'locations': Location.objects.all(),
        'location_id': location_id,
    })


# ---------------------------------------------------------------------------
# Sections génériques (lieux, scènes, monstres, objets, quêtes, origines, paliers)
# ---------------------------------------------------------------------------
@staff_required
def section_list(request, section):
    config = _section(section)
    model = config['model']
    queryset = model.objects.all()
    query = request.GET.get('q', '').strip()
    if query:
        condition = Q()
        for field in config.get('search', []):
            condition |= Q(**{f'{field}__icontains': query})
        queryset = queryset.filter(condition)
    current_filter = None
    filter_options = []
    if config.get('filter'):
        field, filter_model, all_label = config['filter']
        filter_options = [('', all_label)] + [(str(o.pk), str(o)) for o in filter_model.objects.all()]
        current_filter = request.GET.get(field, '')
        if current_filter:
            queryset = queryset.filter(**{f'{field}_id': current_filter})
    page = Paginator(queryset, PER_PAGE).get_page(request.GET.get('page'))
    rows = [{'obj': obj, 'cells': [_cell(obj, path) for _, path in config['columns']]} for obj in page]
    return _render(request, 'panel/ivakar/list.html', {
        'section': section, 'config': config, 'rows': rows, 'page': page, 'query': query,
        'filter_field': config['filter'][0] if config.get('filter') else '',
        'filter_options': filter_options, 'current_filter': current_filter,
    })


def _formsets(config, instance, data=None):
    formsets = []
    for index, spec in enumerate(config['inlines']):
        kwargs = {'instance': instance, 'prefix': f'inline{index}'}
        if spec['initial'] and data is None:
            initial = spec['initial'](instance)
            # Une ligne pré-remplie par élément manquant (sans toucher à la classe partagée).
            formset_class = type('PrefilledFormSet', (spec['formset'],), {'extra': len(initial)})
            kwargs['initial'] = initial
        else:
            formset_class = spec['formset']
        formsets.append({'title': spec['title'], 'formset': formset_class(data, **kwargs)})
    return formsets


def _edit(request, section, instance):
    config = _section(section)
    creating = instance.pk is None
    if request.method == 'POST':
        form = config['form'](request.POST, request.FILES, instance=instance)
        formsets = _formsets(config, instance, request.POST)
        if form.is_valid() and all(f['formset'].is_valid() for f in formsets):
            with transaction.atomic():
                obj = form.save()
                for f in formsets:
                    f['formset'].instance = obj
                    f['formset'].save()
            messages.success(request, f"{config['title']} : « {obj} » enregistré.")
            if config.get('has_choices') and creating:
                return redirect('panel_ivakar_edit', section, obj.pk)
            if 'continue' in request.POST:
                return redirect('panel_ivakar_edit', section, obj.pk)
            return redirect('panel_ivakar_list', section)
        messages.error(request, "Le formulaire contient des erreurs.")
    else:
        initial = {}
        if config.get('filter') and request.GET.get(config['filter'][0]):
            initial[config['filter'][0]] = request.GET.get(config['filter'][0])
        form = config['form'](instance=instance, initial=initial)
        formsets = _formsets(config, instance)
    context = {
        'section': section, 'config': config, 'form': form, 'formsets': formsets, 'obj': instance,
        'creating': creating,
    }
    if config.get('has_choices') and not creating:
        context['choices'] = instance.choices.select_related('test_characteristic').prefetch_related('outcomes')
    return _render(request, 'panel/ivakar/form.html', context)


@staff_required
def section_create(request, section):
    return _edit(request, section, _section(section)['model']())


@staff_required
def section_edit(request, section, pk):
    return _edit(request, section, get_object_or_404(_section(section)['model'], pk=pk))


@staff_required
@require_POST
def section_delete(request, section, pk):
    config = _section(section)
    obj = get_object_or_404(config['model'], pk=pk)
    name = str(obj)
    obj.delete()
    messages.success(request, f"« {name} » supprimé.")
    return redirect('panel_ivakar_list', section)


# ---------------------------------------------------------------------------
# Choix d'une scène et leurs conséquences
# ---------------------------------------------------------------------------
def _choice_page(request, choice, scene):
    creating = choice.pk is None
    outcomes = {result: (choice.outcomes.filter(result=result).first() if not creating else None)
                for result in (Outcome.RESULT_SUCCESS, Outcome.RESULT_FAILURE)}
    if request.method == 'POST':
        form = ChoiceForm(request.POST, instance=choice)
        success = OutcomeForm(request.POST, prefix='success',
                              instance=outcomes['success'] or Outcome(result=Outcome.RESULT_SUCCESS))
        failure = OutcomeForm(request.POST, prefix='failure',
                              instance=outcomes['failure'] or Outcome(result=Outcome.RESULT_FAILURE))
        drop_failure = 'drop_failure' in request.POST
        if form.is_valid() and success.is_valid() and (drop_failure or failure.is_valid()):
            with transaction.atomic():
                choice = form.save(commit=False)
                choice.scene = scene
                choice.save()
                for outcome_form, result in ((success, Outcome.RESULT_SUCCESS), (failure, Outcome.RESULT_FAILURE)):
                    outcome = outcome_form.instance
                    if result == Outcome.RESULT_FAILURE:
                        if drop_failure:
                            if outcome.pk:
                                outcome.delete()
                            continue
                        if not outcome.pk and not outcome_form.has_changed():
                            continue
                    outcome = outcome_form.save(commit=False)
                    outcome.choice = choice
                    outcome.result = result
                    outcome.save()
            messages.success(request, f"Choix « {choice.label} » enregistré.")
            if 'continue' in request.POST:
                return redirect('panel_ivakar_choice_edit', choice.pk)
            return redirect('panel_ivakar_edit', 'scenes', scene.pk)
        messages.error(request, "Le formulaire contient des erreurs.")
    else:
        form = ChoiceForm(instance=choice, initial={'order': scene.choices.count() + 1} if creating else None)
        success = OutcomeForm(prefix='success', instance=outcomes['success'])
        failure = OutcomeForm(prefix='failure', instance=outcomes['failure'])
    return _render(request, 'panel/ivakar/choice_form.html', {
        'section': 'scenes', 'scene': scene, 'choice': choice, 'creating': creating, 'form': form,
        'success': success, 'failure': failure, 'has_failure': outcomes['failure'] is not None,
    })


@staff_required
def choice_create(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id)
    return _choice_page(request, Choice(scene=scene), scene)


@staff_required
def choice_edit(request, pk):
    choice = get_object_or_404(Choice.objects.select_related('scene'), pk=pk)
    return _choice_page(request, choice, choice.scene)


@staff_required
@require_POST
def choice_delete(request, pk):
    choice = get_object_or_404(Choice, pk=pk)
    scene_id = choice.scene_id
    choice.delete()
    messages.success(request, "Choix supprimé.")
    return redirect('panel_ivakar_edit', 'scenes', scene_id)


# ---------------------------------------------------------------------------
# Héros (consultation et dépannage)
# ---------------------------------------------------------------------------
@staff_required
def hero_list(request):
    heroes = Character.objects.select_related('user', 'location', 'origin').order_by('-level', '-xp')
    query = request.GET.get('q', '').strip()
    if query:
        heroes = heroes.filter(Q(name__icontains=query) | Q(user__username__icontains=query))
    page = Paginator(heroes, PER_PAGE).get_page(request.GET.get('page'))
    in_combat = set(Combat.objects.values_list('character_id', flat=True))
    return _render(request, 'panel/ivakar/heroes.html', {
        'section': 'heros', 'page': page, 'query': query, 'in_combat': in_combat,
    })


HERO_ACTIONS = {
    'heal': "PV restaurés",
    'end_combat': "Combat terminé",
    'leave_scene': "Scène quittée",
    'wake': "Héros réveillé",
    'clear_wounds': "Blessures retirées",
}


@staff_required
def hero_detail(request, pk):
    character = get_object_or_404(Character.objects.select_related('user', 'location', 'scene', 'origin'), pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            character = Character.objects.select_for_update().get(pk=pk)
            action = request.POST.get('action')
            if action == 'save':
                _save_hero(request, character)
            elif action in HERO_ACTIONS:
                _hero_action(character, action)
                messages.success(request, f"{HERO_ACTIONS[action]}.")
            elif action == 'remove_wound':
                Wound.objects.filter(character=character, pk=request.POST.get('wound')).delete()
                messages.success(request, "Blessure retirée.")
            elif action == 'delete':
                name = character.name
                character.delete()
                messages.success(request, f"Le héros {name} a été supprimé : son joueur pourra en créer un autre.")
                return redirect('panel_ivakar_heroes')
        return redirect('panel_ivakar_hero', pk)
    return _render(request, 'panel/ivakar/hero.html', {
        'section': 'heros', 'character': character, 'sheet': hero.sheet(character),
        'stats': {CHARACTERISTICS[code][0]: value for code, value in hero.stat_values(character).items()},
        'wounds': Wound.objects.filter(character=character),
        'inventory': InventoryItem.objects.filter(inventory__character=character).select_related('item'),
        'quests': CharacterQuest.objects.filter(character=character).select_related('quest'),
        'combat': Combat.objects.filter(character=character).select_related('monster').first(),
        'locations': Location.objects.all(),
        'flags_text': "\n".join(character.flags or []),
        'log': list(reversed(character.log or [])),
    })


def _save_hero(request, character):
    post = request.POST
    name = post.get('name', '').strip()
    if name:
        character.name = name[:hero.NAME_MAX_LENGTH]
    for field in ('coins', 'hp', 'unspent_points'):
        try:
            setattr(character, field, max(0, int(post.get(field, getattr(character, field)))))
        except (TypeError, ValueError):
            pass
    character.hp = min(character.hp, hero.max_hp(character))
    location = Location.objects.filter(pk=post.get('location')).first()
    if location:
        character.location = location
    character.flags = [line.strip() for line in post.get('flags', '').splitlines() if line.strip()]
    character.show_title = 'show_title' in post
    character.save()
    messages.success(request, "Héros mis à jour.")


def _hero_action(character, action):
    if action == 'heal':
        character.hp = hero.max_hp(character)
    elif action == 'end_combat':
        Combat.objects.filter(character=character).delete()
    elif action == 'leave_scene':
        character.scene = None
    elif action == 'wake':
        character.state = Character.STATE_OK
        character.hp = max(character.hp, 1)
    elif action == 'clear_wounds':
        Wound.objects.filter(character=character).delete()
    hero.add_log(character, "L'équipe d'Ivakar est intervenue sur ton héros.", 'info')
    character.save()


# ---------------------------------------------------------------------------
# Bureau de change (lecture seule)
# ---------------------------------------------------------------------------
@staff_required
def exchange_list(request):
    page = Paginator(CoinExchange.objects.select_related('user'), PER_PAGE).get_page(request.GET.get('page'))
    return _render(request, 'panel/ivakar/exchanges.html', {
        'section': 'change', 'page': page,
        'totals': CoinExchange.objects.aggregate(gold=Sum('gold_spent'), coins=Sum('coins_received')),
    })


# ---------------------------------------------------------------------------
# Carte du monde : placement des lieux et fond de carte
# ---------------------------------------------------------------------------
@staff_required
def world_map(request):
    world = WorldMap.current()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'positions':
            moved = 0
            for location in Location.objects.all():
                x, y = request.POST.get(f'x_{location.pk}'), request.POST.get(f'y_{location.pk}')
                if x is None or y is None:
                    continue
                try:
                    x, y = (max(0, min(MAP_SIZE, int(float(v)))) for v in (x, y))
                except (TypeError, ValueError):
                    continue
                if (location.map_x, location.map_y) != (x, y):
                    Location.objects.filter(pk=location.pk).update(map_x=x, map_y=y)
                    moved += 1
            messages.success(request, f"Positions enregistrées ({moved} lieu{'x' if moved > 1 else ''} déplacé"
                                      f"{'s' if moved > 1 else ''}).")
        elif action == 'place':
            location = Location.objects.filter(pk=request.POST.get('location'), map_x=None).first()
            if location:
                Location.objects.filter(pk=location.pk).update(map_x=MAP_SIZE // 2, map_y=MAP_SIZE // 2)
                messages.success(request, f"« {location.name} » est placé au centre : fais-le glisser à sa place.")
        elif action == 'unplace':
            Location.objects.filter(pk=request.POST.get('location')).update(map_x=None, map_y=None)
            messages.success(request, "Lieu retiré de la carte.")
        elif action == 'background' and request.FILES.get('image'):
            world.image = request.FILES['image']
            world.save()
            messages.success(request, "Nouveau fond de carte enregistré.")
        elif action == 'reset_background' and world.pk:
            world.image = ''
            world.save()
            messages.success(request, "Le parchemin fourni est rétabli.")
        return redirect('panel_ivakar_map')
    return _render(request, 'panel/ivakar/map.html', {
        'section': 'carte', 'map': map_for(None), 'background': world.background_url,
        'custom_background': world.has_custom_background if world.pk else False,
        'unplaced': Location.objects.filter(Q(map_x=None) | Q(map_y=None)),
    })


# ---------------------------------------------------------------------------
# Modération de la taverne
# ---------------------------------------------------------------------------
@staff_required
def tavern_moderation(request):
    if request.method == 'POST':
        message = LocationMessage.objects.filter(pk=request.POST.get('message')).first()
        action = request.POST.get('action')
        if message and action == 'hide':
            message.is_hidden = True
            message.save(update_fields=['is_hidden'])
            messages.success(request, "Message masqué.")
        elif message and action == 'show':
            message.is_hidden = False
            message.save(update_fields=['is_hidden'])
            messages.success(request, "Message rétabli.")
        elif message and action == 'delete':
            message.delete()
            messages.success(request, "Message supprimé.")
        return redirect(request.get_full_path())
    queryset = LocationMessage.objects.select_related('location', 'character__user')
    location = request.GET.get('lieu', '')
    if location:
        queryset = queryset.filter(location_id=location)
    query = request.GET.get('q', '').strip()
    if query:
        queryset = queryset.filter(Q(text__icontains=query) | Q(character__name__icontains=query)
                                   | Q(character__user__username__icontains=query))
    page = Paginator(queryset, 50).get_page(request.GET.get('page'))
    return _render(request, 'panel/ivakar/tavern.html', {
        'section': 'taverne', 'page': page, 'query': query, 'locations': Location.objects.all(),
        'current_filter': location, 'filter_field': 'lieu',
    })
