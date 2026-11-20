from django.conf import settings
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import rpg_access, rpg_player
from .engine import RpgError
from .engine import character as hero
from .engine import combat as fight
from .engine import economy, rewards as site_rewards, scenes, world
from .engine import duel as duel_engine
from .engine import events, social, wounds
from .engine.worldmap import map_for
from .engine.rules import DIFFICULTY_LABELS, MAX_LEVEL, POINTS_PER_LEVEL, STAT_CAP
from .models import Character, CharacterQuest, Duel, InventoryItem, Location, Origin, Trade, WorldMap, Wound

PLAY = 'rpg_play'


def _meta(title, description=""):
    return {
        'page_title': f"{title} - Ivakar - {settings.SITE_NAME}",
        'page_heading': title,
        'page_description': description or (
            "Ivakar, le RPG textuel de la communauté : explore un monde de brumes, "
            "fais tes choix, combats et débloque des récompenses sur le site."
        ),
    }


def _character(request):
    return Character.objects.select_related('location', 'scene').filter(user=request.user).first()


def _run(request, action, *args, success=None, to=PLAY):
    """Exécute une action du moteur ; une erreur s'affiche au joueur."""
    try:
        action(*args)
    except RpgError as error:
        messages.error(request, str(error))
    else:
        if success:
            messages.success(request, success)
    return redirect(to)


def player_view(view_func):
    """Page de jeu qui exige un héros : sinon direction la création."""
    @rpg_player
    def wrapper(request, *args, **kwargs):
        character = _character(request)
        if character is None:
            return redirect('rpg_create')
        social.touch(character)
        return view_func(request, character, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _hud(character):
    return {
        'character': character,
        'sheet': hero.sheet(character),
        'wounds': list(Wound.objects.filter(character=character)),
        'difficulty_labels': DIFFICULTY_LABELS,
        'pending_trades': Trade.objects.filter(receiver=character, status=Trade.STATUS_PENDING).count(),
        'duels_waiting': duel_engine.open_duels(character).filter(
            Q(status=Duel.STATUS_PENDING, opponent=character) | Q(status=Duel.STATUS_ACTIVE, turn=character)).count(),
        'world_event': events.current_event(),
    }


# ---------------------------------------------------------------------------
# Présentation et création
# ---------------------------------------------------------------------------
@rpg_access
def home(request):
    character = _character(request) if request.user.is_authenticated else None
    heroes = Character.objects.select_related('user').order_by('-level', '-xp')[:10]
    return render(request, 'rpg/home.html', {
        **_meta("Ivakar"),
        'character': character,
        'heroes': heroes,
        'track': site_rewards.reward_track(character),
        'is_open': getattr(settings, 'RPG_OPEN', False),
        'banner': next((loc.visual_url for loc in Location.objects.filter(is_start=True)[:1]), ''),
        'world_event': events.current_event(),
    })


@rpg_player
def create(request):
    if _character(request):
        return redirect(PLAY)
    characteristics = hero.ensure_characteristics()
    form = {'name': '', 'origin': ''}
    if request.method == 'POST':
        form = {'name': request.POST.get('name', ''), 'origin': request.POST.get('origin', '')}
        try:
            hero.create_character(request.user, form['name'], form['origin'])
        except RpgError as error:
            messages.error(request, str(error))
        else:
            return redirect(PLAY)
    origins = []
    for origin in Origin.objects.filter(is_active=True).prefetch_related('values__characteristic'):
        values = {row.characteristic_id: row.value for row in origin.values.all()}
        origins.append({'obj': origin, 'values': [(c, values.get(c.pk, '—')) for c in characteristics]})
    return render(request, 'rpg/create.html', {
        **_meta("Créer ton héros"),
        'origins': origins,
        'form': form,
        'name_max_length': hero.NAME_MAX_LENGTH,
        'points_per_level': POINTS_PER_LEVEL,
        'max_level': MAX_LEVEL,
    })


# ---------------------------------------------------------------------------
# Jeu
# ---------------------------------------------------------------------------
@player_view
def play(request, character):
    context = {**_meta(character.location.name if character.location else "Ivakar"), **_hud(character)}
    combat = fight.current_combat(character)
    if character.is_ko:
        context['mode'] = 'ko'
    elif combat:
        context.update({
            'mode': 'combat',
            'combat': combat,
            'consumables': InventoryItem.objects.filter(
                inventory__character=character, item__kind='consumable', quantity__gt=0,
            ).select_related('item'),
        })
    elif character.scene_id:
        choices = scenes.choices_for(character)
        context.update({
            'mode': 'scene',
            'scene': character.scene,
            'choices': choices,
            'can_leave': not any(reason is None for _, reason in choices),
        })
    else:
        context.update({
            'mode': 'location', 'exits': world.exits_for(character),
            'present': social.present_heroes(character),
            'tavern': social.tavern(character.location),
            'message_max_length': social.MESSAGE_MAX_LENGTH,
        })
    context['log'] = list(reversed(character.log or []))
    return render(request, 'rpg/play.html', context)


@require_POST
@player_view
def explore(request, character):
    return _run(request, world.explore, character)


@require_POST
@player_view
def move(request, character, exit_id):
    return _run(request, world.move, character, exit_id)


@require_POST
@player_view
def choose(request, character, choice_id):
    return _run(request, scenes.choose, character, choice_id)


@require_POST
@player_view
def leave_scene(request, character):
    return _run(request, scenes.leave_scene, character)


@require_POST
@player_view
def combat_action(request, character):
    action = request.POST.get('action', '')
    item_id = request.POST.get('item') or None
    return _run(request, fight.act, character, action, item_id)


@require_POST
@player_view
def wake_up(request, character):
    return _run(request, wounds.wake_up, character)


@require_POST
@player_view
def rest(request, character):
    return _run(request, hero.rest, character)


# ---------------------------------------------------------------------------
# Héros, inventaire, quêtes
# ---------------------------------------------------------------------------
@player_view
def sheet(request, character):
    stats = hero.stat_values(character)
    characteristics = [{'obj': c, 'value': stats.get(c.code, 0), 'bonus': stats.get(c.code, 0) // 3}
                       for c in hero.ensure_characteristics()]
    return render(request, 'rpg/sheet.html', {
        **_meta("Fiche du héros"), **_hud(character),
        'stat_cap': STAT_CAP,
        'max_level': MAX_LEVEL,
        'characteristics': characteristics,
        'title': site_rewards.current_title(character, respect_visibility=False),
    })


@require_POST
@player_view
def spend_point(request, character):
    return _run(request, hero.spend_point, character, request.POST.get('code', ''), to='rpg_sheet')


@require_POST
@player_view
def toggle_title(request, character):
    character.show_title = not character.show_title
    character.save(update_fields=['show_title'])
    messages.success(request, "Ton titre est affiché sur le site." if character.show_title
                     else "Ton titre n'est plus affiché sur le site.")
    return redirect('rpg_sheet')


@player_view
def inventory(request, character):
    return render(request, 'rpg/inventory.html', {
        **_meta("Inventaire"), **_hud(character),
        'entries': InventoryItem.objects.filter(inventory__character=character, quantity__gt=0)
        .select_related('item'),
    })


@require_POST
@player_view
def equip(request, character, item_id):
    return _run(request, hero.toggle_equip, character, item_id, to='rpg_inventory')


@require_POST
@player_view
def use(request, character, item_id):
    return _run(request, hero.use_item, character, item_id, to='rpg_inventory')


@player_view
def world_map(request, character):
    return render(request, 'rpg/map.html', {
        **_meta("Les plaines d’Agasur"), **_hud(character),
        'map': map_for(character),
        'background': WorldMap.current().background_url,
    })


@player_view
def quests(request, character):
    entries = CharacterQuest.objects.filter(character=character).select_related('quest')
    return render(request, 'rpg/quests.html', {
        **_meta("Journal de quêtes"), **_hud(character),
        'active': [e for e in entries if e.status == CharacterQuest.STATUS_ACTIVE],
        'done': [e for e in entries if e.status == CharacterQuest.STATUS_DONE],
    })


# ---------------------------------------------------------------------------
# Économie
# ---------------------------------------------------------------------------
@player_view
def merchant(request, character):
    if not character.location or not character.location.has_merchant:
        messages.error(request, "Il n'y a pas de marchand ici.")
        return redirect(PLAY)
    return render(request, 'rpg/merchant.html', {
        **_meta("Le marchand"), **_hud(character),
        'wares': economy.wares(character),
        'sellable': [e for e in InventoryItem.objects.filter(
            inventory__character=character, quantity__gt=0).select_related('item') if e.item.is_sellable],
    })


@require_POST
@player_view
def buy(request, character, item_id):
    return _run(request, economy.buy, character, item_id, to='rpg_merchant')


@require_POST
@player_view
def sell(request, character, item_id):
    return _run(request, economy.sell, character, item_id, to='rpg_merchant')


@player_view
def exchange(request, character):
    if request.method == 'POST':
        try:
            _, gold, coins = economy.exchange(request.user, request.POST.get('pack'))
        except RpgError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"{gold} or du site échangés contre {coins} écus.")
        return redirect('rpg_exchange')
    return render(request, 'rpg/exchange.html', {
        **_meta("Bureau de change"), **_hud(character),
        'packs': [{'index': i, 'gold': g, 'coins': c, 'affordable': request.user.gold >= g}
                  for i, (g, c) in enumerate(economy.EXCHANGE_PACKS)],
    })


@player_view
def rewards(request, character):
    return render(request, 'rpg/rewards.html', {
        **_meta("Récompenses sur le site"), **_hud(character),
        'track': site_rewards.reward_track(character),
    })
