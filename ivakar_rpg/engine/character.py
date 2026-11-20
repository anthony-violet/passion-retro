"""Le héros : création, caractéristiques, statistiques dérivées, XP, PV, inventaire.

Règles validées : ``engine/rules.py``. Les formules marquées PROVISOIRE ne sont
pas encore tranchées par les règles d'Ivakar (voir ``REGLES.md``).
"""
from django.db import transaction
from django.db.models import F

from ..models import (
    Character, CharacterCharacteristic, Characteristic, Combat, Inventory, InventoryItem, Item, Location, Origin,
)
from . import RpgError
from .rules import CHARACTERISTICS, MAX_LEVEL, POINTS_PER_LEVEL, START_MAX, START_MIN, STAT_CAP, bonus

LOG_SIZE = 10
NAME_MAX_LENGTH = 30
STARTING_COINS = 15
# Paquetage de départ (slug -> quantité), donné s'il existe en base. Les armes sont équipées.
STARTING_ITEMS = {'baton-noueux': 1, 'potion-soin': 2}

# PROVISOIRE — points de vie : 10 + Constitution + 2 par niveau au-delà du premier.
HP_BASE = 10
HP_PER_LEVEL = 2


def ensure_characteristics():
    """Crée les sept caractéristiques validées si elles n'existent pas encore."""
    for code, (name, description, order) in CHARACTERISTICS.items():
        Characteristic.objects.get_or_create(
            code=code, defaults={'name': name, 'description': description, 'order': order},
        )
    return list(Characteristic.objects.filter(is_hidden=False))


def xp_for_level(level):
    """PROVISOIRE — XP cumulée pour atteindre ``level`` : 0, 50, 150, 300, 500…"""
    return 25 * (level - 1) * level


def lock(character):
    """Relit le personnage en le verrouillant (à appeler dans ``transaction.atomic``)."""
    return Character.objects.select_for_update().select_related('location', 'scene').get(pk=character.pk)


def visit(character, location):
    """Déplace le héros et marque le lieu comme découvert (personnage verrouillé, non sauvegardé)."""
    character.location = location
    if location is not None and location.pk not in (character.visited or []):
        character.visited = list(character.visited or []) + [location.pk]


def start_location():
    location = Location.objects.filter(is_start=True).order_by('order').first()
    if location is None:
        raise RpgError("Le monde d'Ivakar n'est pas encore prêt : aucun lieu de départ n'existe.")
    return location


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------
def add_log(character, text, kind='info'):
    """Ajoute une ligne au récit. ``kind`` : info, good, bad, story (BBCode de l'équipe)."""
    if not text:
        return
    entries = list(character.log or [])
    entries.append({'text': text, 'kind': kind})
    character.log = entries[-LOG_SIZE:]


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------
def stat_values(character):
    """``{code: valeur}`` des caractéristiques du héros."""
    values = {code: 0 for code in CHARACTERISTICS}
    for row in CharacterCharacteristic.objects.filter(character=character).select_related('characteristic'):
        values[row.characteristic.code] = row.value
    return values


def equipped_items(character):
    return [entry.item for entry in InventoryItem.objects.filter(
        inventory__character=character, equipped=True, quantity__gt=0,
    ).select_related('item')]


def sheet(character):
    """Statistiques dérivées, calculées une fois. Tout ce qui suit ``stats`` est PROVISOIRE."""
    stats = stat_values(character)
    gear = equipped_items(character)
    max_hp = (HP_BASE + stats.get('constitution', 0) + HP_PER_LEVEL * (character.level - 1)
              + sum(item.hp_bonus for item in gear))
    return {
        'stats': stats,
        'gear': gear,
        # Dégâts infligés : 1D6 + ⌊Force ÷ 3⌋ + bonus de l'arme.
        'damage_bonus': bonus(stats.get('force', 0)) + sum(item.attack_bonus for item in gear),
        # Dégâts absorbés par l'armure.
        'armor': max(0, sum(item.defense_bonus for item in gear)),
        'dexterity': stats.get('dexterite', 0),
        'max_hp': max(1, max_hp),
        'xp_current_level': xp_for_level(character.level),
        'xp_next_level': xp_for_level(min(character.level + 1, MAX_LEVEL)),
    }


def max_hp(character):
    return sheet(character)['max_hp']


# ---------------------------------------------------------------------------
# Création
# ---------------------------------------------------------------------------
def origin_values(origin):
    """``{code: valeur}`` de départ d'une origine (1 à 20 inclus par caractéristique)."""
    return {row.characteristic.code: row.value for row in origin.values.select_related('characteristic')}


def create_character(user, name, origin_id):
    """Crée le héros de ``user``. Ses caractéristiques de départ découlent de l'origine choisie."""
    name = (name or '').strip()
    if not name:
        raise RpgError("Ton héros a besoin d'un nom.")
    if len(name) > NAME_MAX_LENGTH:
        raise RpgError(f"Le nom ne doit pas dépasser {NAME_MAX_LENGTH} caractères.")
    try:
        origin = Origin.objects.get(pk=int(origin_id), is_active=True)
    except (TypeError, ValueError, Origin.DoesNotExist):
        raise RpgError("Choisis l'origine de ton héros.")

    characteristics = ensure_characteristics()
    values = origin_values(origin)
    for characteristic in characteristics:
        value = values.get(characteristic.code)
        if value is None or not START_MIN <= value <= START_MAX:
            raise RpgError(f"L'origine {origin.name} est incomplète : prévenez l'équipe.")

    location = start_location()
    with transaction.atomic():
        if Character.objects.select_for_update().filter(user=user).exists():
            raise RpgError("Tu as déjà un héros à Ivakar.")
        character = Character.objects.create(user=user, name=name, origin=origin, location=location, hp=1,
                                             coins=STARTING_COINS, visited=[location.pk])
        inventory = Inventory.objects.create(character=character)
        CharacterCharacteristic.objects.bulk_create([
            CharacterCharacteristic(character=character, characteristic=characteristic,
                                    value=values[characteristic.code])
            for characteristic in characteristics
        ])
        for item in Item.objects.filter(slug__in=STARTING_ITEMS):
            InventoryItem.objects.create(inventory=inventory, item=item,
                                         quantity=STARTING_ITEMS[item.slug], equipped=item.is_equippable)
        character.hp = max_hp(character)
        add_log(character, f"{name} arrive à {location.name}. L'aventure commence.", 'good')
        character.save()
    return character


# ---------------------------------------------------------------------------
# Progression
# ---------------------------------------------------------------------------
def gain_xp(character, amount):
    """Ajoute de l'XP (personnage verrouillé, non sauvegardé). Renvoie les niveaux gagnés.

    Chaque passage de niveau donne 3 points de progression, répartis librement par
    le joueur. Aucune caractéristique n'augmente automatiquement.
    """
    from django.urls import reverse

    from .notifications import notify
    from .rewards import grant_level_rewards

    if amount <= 0:
        return 0
    character.xp += amount
    old_level = character.level
    gained = 0
    while character.level < MAX_LEVEL and character.xp >= xp_for_level(character.level + 1):
        character.level += 1
        character.unspent_points += POINTS_PER_LEVEL
        gained += 1
    if gained:
        character.hp = max_hp(character)  # PROVISOIRE : PV restaurés au passage de niveau
        add_log(character, f"Niveau {character.level} ! {POINTS_PER_LEVEL * gained} points de progression "
                           "à répartir.", 'good')
        character.save()
        notify(character, 'level_up', f"Niveau {character.level} !",
               f"{POINTS_PER_LEVEL * gained} points de progression à répartir librement.", reverse('rpg_sheet'))
        from .skills import notify_learned
        notify_learned(character, old_level)
        grant_level_rewards(character)
    return gained


def change_hp(character, delta, rng=None):
    """Soigne ou blesse. Renvoie ``True`` si le héros tombe à 0 PV (KO)."""
    from .wounds import knock_out

    if delta == 0:
        return False
    character.hp = max(0, min(max_hp(character), character.hp + delta))
    if character.hp == 0:
        knock_out(character, rng=rng)
        return True
    return False


def change_coins(character, delta):
    character.coins = max(0, character.coins + delta)


def spend_point(character, code):
    """Investit un point de progression (plafond absolu : 100)."""
    with transaction.atomic():
        character = lock(character)
        if character.unspent_points <= 0:
            raise RpgError("Tu n'as aucun point à répartir.")
        row = (CharacterCharacteristic.objects.select_for_update().select_related('characteristic')
               .filter(character=character, characteristic__code=code, characteristic__is_hidden=False).first())
        if row is None:
            raise RpgError("Caractéristique inconnue.")
        if row.value >= STAT_CAP:
            raise RpgError(f"{row.characteristic.name} a atteint son plafond absolu ({STAT_CAP}).")
        before = max_hp(character)
        row.value += 1
        row.save(update_fields=['value'])
        character.unspent_points -= 1
        character.hp += max(0, max_hp(character) - before)
        character.save()
    return character


def rest(character):
    """Nuit à l'auberge : PV au maximum et blessures soignées d'un degré (PROVISOIRE)."""
    from .wounds import treat_all

    with transaction.atomic():
        character = lock(character)
        ensure_free(character)
        location = character.location
        if not location or not location.has_inn:
            raise RpgError("Il n'y a pas d'auberge ici.")
        price = location.inn_price
        if character.coins >= price:
            character.coins -= price
            add_log(character, f"Une nuit à l'auberge ({price} écus). Tu as récupéré.", 'good')
        else:
            add_log(character, "L'aubergiste refuse de laisser un voyageur dormir dehors et t'offre la nuit.", 'good')
        character.hp = max_hp(character)
        treat_all(character)
        character.save()
    return character


def ensure_free(character):
    """Refuse l'action si le héros est KO, en combat ou au milieu d'une scène."""
    if character.is_ko:
        raise RpgError("Tu es inconscient.")
    if Combat.objects.filter(character=character).exists():
        raise RpgError("Tu es en plein combat !")
    if character.scene_id:
        raise RpgError("Termine d'abord ce qui se passe ici.")


# ---------------------------------------------------------------------------
# Inventaire
# ---------------------------------------------------------------------------
def inventory_of(character):
    inventory, _ = Inventory.objects.get_or_create(character=character)
    return inventory


def owned_item_ids(character):
    return set(InventoryItem.objects.filter(inventory__character=character, quantity__gt=0)
               .values_list('item_id', flat=True))


def has_item(character, item):
    return InventoryItem.objects.filter(inventory__character=character, item=item, quantity__gt=0).exists()


def add_item(character, item, quantity=1):
    inventory = inventory_of(character)
    entry, created = InventoryItem.objects.get_or_create(
        inventory=inventory, item=item, defaults={'quantity': quantity},
    )
    if not created:
        InventoryItem.objects.filter(pk=entry.pk).update(quantity=F('quantity') + quantity)


def remove_item(character, item, quantity=1):
    """Retire ``quantity`` exemplaires. Renvoie ``False`` si le héros n'en a pas assez."""
    entry = (InventoryItem.objects.select_for_update()
             .filter(inventory__character=character, item=item).first())
    if entry is None or entry.quantity < quantity:
        return False
    if entry.quantity == quantity:
        entry.delete()
    else:
        entry.quantity -= quantity
        entry.save(update_fields=['quantity'])
    return True


def toggle_equip(character, item_id):
    """Équipe l'objet (en retirant l'éventuel objet du même type) ou le retire."""
    with transaction.atomic():
        character = lock(character)
        entry = (InventoryItem.objects.select_for_update().select_related('item')
                 .filter(inventory__character=character, item_id=item_id, quantity__gt=0).first())
        if entry is None:
            raise RpgError("Tu ne possèdes pas cet objet.")
        if not entry.item.is_equippable:
            raise RpgError("Cet objet ne s'équipe pas.")
        if entry.equipped:
            entry.equipped = False
            add_log(character, f"Tu ranges {entry.item.name}.")
        else:
            InventoryItem.objects.filter(inventory__character=character, item__kind=entry.item.kind,
                                         equipped=True).update(equipped=False)
            entry.equipped = True
            add_log(character, f"Tu t'équipes de {entry.item.name}.")
        entry.save(update_fields=['equipped'])
        character.hp = min(character.hp, max_hp(character))
        character.save()
    return character


def consume(character, item_id):
    """Utilise un consommable (personnage verrouillé, non sauvegardé). Renvoie les PV rendus."""
    item = Item.objects.filter(pk=item_id).first()
    if item is None or item.kind != Item.KIND_CONSUMABLE:
        raise RpgError("Cet objet ne s'utilise pas.")
    if not remove_item(character, item):
        raise RpgError("Tu ne possèdes pas cet objet.")
    heal = item.heal
    before = character.hp
    character.hp = min(max_hp(character), character.hp + heal)
    restored = character.hp - before
    add_log(character, f"Tu utilises {item.name} : +{restored} PV.", 'good')
    return restored


def use_item(character, item_id):
    """Utilise un consommable hors combat."""
    with transaction.atomic():
        character = lock(character)
        if character.is_ko:
            raise RpgError("Tu es inconscient.")
        if Combat.objects.filter(character=character).exists():
            raise RpgError("En combat, utilise l'objet depuis l'écran de combat.")
        consume(character, item_id)
        character.save()
    return character
