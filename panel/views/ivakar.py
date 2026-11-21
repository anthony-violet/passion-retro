"""Panel — Ivakar : tout le contenu du RPG, les héros et le bureau de change."""
import json

from django.conf import settings
from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
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


def _is_popup(request):
    return request.GET.get('popup') == '1'


def _render(request, template, context):
    popup = _is_popup(request)
    return render(request, template, {
        'ivakar_sections': _nav(),
        'popup': popup,
        'base_template': 'panel/ivakar/popup_base.html' if popup else 'panel/ivakar/base.html',
        'known_flags': [flag for flag, _ in scenario_tree.flag_index()],
        **context,
    })


def _popup_done(request, section, obj):
    """Fin d'une création ou d'une modification en fenêtre : prévient la page d'origine."""
    return render(request, 'panel/ivakar/popup_done.html', {'payload': {
        'type': 'ivakar-saved', 'section': section, 'id': obj.pk, 'label': str(obj),
    }})


def _page_context(section, obj):
    """Valeurs proposées aux créations faites depuis cette page (lieu, PNJ…), en JSON pour le script."""
    if obj is None or not obj.pk:
        return {}
    if section == 'scenes':
        return {'location': obj.location_id, 'npc': obj.npc_id, 'locations': obj.location_id}
    if section == 'lieux':
        return {'location': obj.pk, 'locations': obj.pk}
    if section == 'pnj':
        first = obj.locations.first()
        return {'npc': obj.pk, 'location': first.pk if first else None, 'locations': first.pk if first else None}
    return {}


def _initial_from_query(request, form_class):
    """Pré-remplissage d'une création à partir de l'adresse (ex. ``?location=3&npc=5``)."""
    initial = {}
    for name, field in form_class.base_fields.items():
        if name not in request.GET:
            continue
        if isinstance(field, forms.ModelMultipleChoiceField):
            initial[name] = request.GET.getlist(name)
        else:
            initial[name] = request.GET.get(name)
    return initial


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


@staff_required
@require_POST
def branch_scene(request, choice_id, result):
    """Depuis l'arbre : crée en ébauche la scène suivante d'une branche (réussite ou échec) et la relie."""
    from ivakar_rpg.authoring import stub_scene

    choice = get_object_or_404(Choice.objects.select_related('scene'), pk=choice_id)
    if result not in (Outcome.RESULT_SUCCESS, Outcome.RESULT_FAILURE):
        raise Http404
    title = request.POST.get('title', '').strip()
    target = reverse('panel_ivakar_tree')
    location = request.POST.get('lieu', '')
    if location.isdigit():
        target += f'?lieu={location}'
    if not title:
        messages.error(request, "Donne un titre à la nouvelle scène.")
        return redirect(target)
    outcome = Outcome.objects.filter(choice=choice, result=result).first() or Outcome(choice=choice, result=result)
    if outcome.next_scene_id:
        messages.error(request, "Cette branche mène déjà à une scène.")
        return redirect(target)
    with transaction.atomic():
        scene = stub_scene(title, choice.scene.location, choice.scene.npc)
        outcome.next_scene = scene
        outcome.save()
    messages.success(request, f"Ébauche « {scene.title} » créée et reliée : complète-la quand tu veux.")
    return redirect(f'{target}#scene-{scene.pk}')


@staff_required
def quest_wizard(request):
    from panel.ivakar_wizard import QuestWizardForm, build_quest

    form = QuestWizardForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quest, npc, location = build_quest(form.cleaned_data)
        messages.success(request, f"Quête « {quest.title} » créée : {npc.name} la propose, l'objectif attend à "
                                  f"{form.cleaned_data['objective_location'].name}. Tout est modifiable ci-dessous.")
        target = reverse('panel_ivakar_tree')
        return redirect(f"{target}?lieu={location.pk}" if location else target)
    return _render(request, 'panel/ivakar/quest_wizard.html', {'section': 'arbre', 'form': form})


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
            queryset = queryset.filter(**{field: current_filter}).distinct()
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
    from ivakar_rpg.usages import usages

    config = _section(section)
    creating = instance.pk is None
    data = request.POST if request.method == 'POST' else None
    if data is not None:
        form = config['form'](data, request.FILES, instance=instance)
    else:
        form = config['form'](instance=instance, initial=_initial_from_query(request, config['form']))
    formsets = _formsets(config, instance, data)
    blocks = _choice_blocks(instance, data) if config.get('has_choices') else []
    if data is not None:
        active = [b for b in blocks if _block_is_active(b)]
        if form.is_valid() and all(f['formset'].is_valid() for f in formsets) \
                and all(_block_is_valid(b) for b in active):
            with transaction.atomic():
                obj = form.save()
                for f in formsets:
                    f['formset'].instance = obj
                    f['formset'].save()
                for block in blocks:
                    if block['delete'] and block['choice'].pk:
                        block['choice'].delete()
                for block in active:
                    _save_block(block, obj)
            if _is_popup(request):
                return _popup_done(request, section, obj)
            messages.success(request, f"{config['title']} : « {obj} » enregistré.")
            if 'continue' in request.POST or (config.get('has_choices') and creating):
                return redirect('panel_ivakar_edit', section, obj.pk)
            return redirect('panel_ivakar_list', section)
        messages.error(request, "Le formulaire contient des erreurs.")
    context = {
        'section': section, 'config': config, 'form': form, 'formsets': formsets, 'obj': instance,
        'creating': creating, 'page_context_json': json.dumps(_page_context(section, instance)),
        'usages': usages(instance) if not creating else [],
    }
    if config.get('has_choices'):
        context['choice_blocks'] = blocks
        context['new_count'] = sum(1 for b in blocks if b['new'])
        context['new_block'] = _block('new__i__', Choice(scene=instance), {}, None, new=True)
    return _render(request, 'panel/ivakar/form.html', context)


# ---------------------------------------------------------------------------
# Choix d'une scène, édités sur la page de la scène
# ---------------------------------------------------------------------------
MAX_NEW_CHOICES = 30


def _block(prefix, choice, outcomes, data, new=False):
    def bound(form_class, sub_prefix, instance):
        return form_class(data, prefix=sub_prefix, instance=instance) if data is not None \
            else form_class(prefix=sub_prefix, instance=instance)

    return {
        'prefix': prefix, 'choice': choice, 'new': new,
        'form': bound(ChoiceForm, prefix, choice),
        'success': bound(OutcomeForm, f'{prefix}-s', outcomes.get(Outcome.RESULT_SUCCESS)
                         or Outcome(result=Outcome.RESULT_SUCCESS)),
        'failure': bound(OutcomeForm, f'{prefix}-f', outcomes.get(Outcome.RESULT_FAILURE)
                         or Outcome(result=Outcome.RESULT_FAILURE)),
        'has_failure': Outcome.RESULT_FAILURE in outcomes,
        'delete': data is not None and f'{prefix}-delete' in data,
        'drop_failure': data is not None and f'{prefix}-drop_failure' in data,
    }


def _choice_blocks(scene, data):
    blocks = []
    if scene.pk:
        for choice in scene.choices.prefetch_related('outcomes').order_by('order', 'pk'):
            outcomes = {o.result: o for o in choice.outcomes.all()}
            blocks.append(_block(f'ch{choice.pk}', choice, outcomes, data))
    try:
        count = min(int((data or {}).get('new_choices', 0)), MAX_NEW_CHOICES)
    except (TypeError, ValueError):
        count = 0
    for index in range(count):
        blocks.append(_block(f'new{index}', Choice(scene=scene if scene.pk else None), {}, data, new=True))
    return blocks


def _block_is_active(block):
    """Un choix existant est enregistré (sauf suppression) ; un nouveau seulement s'il a été rempli."""
    if block['delete']:
        return False
    if block['new']:
        return block['form'].has_changed() or block['success'].has_changed()
    return True


def _block_is_valid(block):
    ok = block['form'].is_valid() & block['success'].is_valid()
    if not block['drop_failure']:
        ok &= block['failure'].is_valid()
    return ok


def _save_block(block, scene):
    choice = block['form'].save(commit=False)
    choice.scene = scene
    choice.save()
    _save_outcomes(choice, scene, block['success'], block['failure'], block['drop_failure'])


def _save_outcomes(choice, scene, success, failure, drop_failure):
    for outcome_form, result in ((success, Outcome.RESULT_SUCCESS), (failure, Outcome.RESULT_FAILURE)):
        outcome = outcome_form.instance
        if result == Outcome.RESULT_FAILURE:
            if drop_failure:
                if outcome.pk:
                    outcome.delete()
                continue
            if not outcome.pk and not outcome_form.has_changed():
                continue
        outcome_form.create_stub(scene)
        outcome = outcome_form.save(commit=False)
        outcome.choice = choice
        outcome.result = result
        outcome.save()


@xframe_options_sameorigin
@staff_required
def section_create(request, section):
    return _edit(request, section, _section(section)['model']())


@xframe_options_sameorigin
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
                _save_outcomes(choice, scene, success, failure, drop_failure)
            if _is_popup(request):
                return _popup_done(request, 'choix', choice)
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
        'page_context_json': json.dumps(_page_context('scenes', scene)),
    })


@xframe_options_sameorigin
@staff_required
def choice_create(request, scene_id):
    scene = get_object_or_404(Scene, pk=scene_id)
    return _choice_page(request, Choice(scene=scene), scene)


@xframe_options_sameorigin
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
