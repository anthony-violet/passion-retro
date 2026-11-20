"""Écus : bureau de change (or du site → écus, sens unique) et marchand."""
from django.db import transaction
from django.db.models import F

from ..models import Character, CoinExchange, InventoryItem, Item
from . import RpgError
from .character import add_item, add_log, ensure_free, lock, remove_item

# (or du site dépensé, écus reçus). Les gros paquets sont un peu plus généreux.
EXCHANGE_PACKS = [(10, 100), (50, 550), (100, 1200)]


def exchange(user, pack_index):
    """Convertit de l'or du site en écus. Il n'existe volontairement aucune conversion inverse."""
    from users.models import User

    try:
        gold, coins = EXCHANGE_PACKS[int(pack_index)]
    except (TypeError, ValueError, IndexError):
        raise RpgError("Ce paquet n'existe pas.")
    with transaction.atomic():
        character = Character.objects.select_for_update().filter(user=user).first()
        if character is None:
            raise RpgError("Crée d'abord ton héros.")
        debited = User.objects.filter(pk=user.pk, gold__gte=gold).update(gold=F('gold') - gold)
        if not debited:
            raise RpgError(f"Il te faut {gold} pièces d'or du site pour ce paquet.")
        character.coins += coins
        add_log(character, f"Bureau de change : {gold} or du site → {coins} écus.", 'good')
        character.save()
        CoinExchange.objects.create(user=user, gold_spent=gold, coins_received=coins)
    user.refresh_from_db(fields=['gold'])
    return character, gold, coins


def _ensure_merchant(character):
    ensure_free(character)
    if not character.location or not character.location.has_merchant:
        raise RpgError("Il n'y a pas de marchand ici.")


def wares(character):
    if not character.location or not character.location.has_merchant:
        return Item.objects.none()
    return character.location.wares.all()


def buy(character, item_id):
    with transaction.atomic():
        character = lock(character)
        _ensure_merchant(character)
        item = character.location.wares.filter(pk=item_id).first()
        if item is None:
            raise RpgError("Le marchand ne vend pas cet objet.")
        if character.coins < item.price:
            raise RpgError(f"Il te faut {item.price} écus pour {item.name}.")
        character.coins -= item.price
        add_item(character, item)
        add_log(character, f"Tu achètes {item.name} pour {item.price} écus.")
        character.save()
    return character


def sell(character, item_id):
    with transaction.atomic():
        character = lock(character)
        _ensure_merchant(character)
        entry = (InventoryItem.objects.select_for_update().select_related('item')
                 .filter(inventory__character=character, item_id=item_id, quantity__gt=0).first())
        if entry is None:
            raise RpgError("Tu ne possèdes pas cet objet.")
        item = entry.item
        if not item.is_sellable:
            raise RpgError("Le marchand n'en veut pas.")
        if entry.equipped and entry.quantity == 1:
            raise RpgError(f"Range d'abord {item.name} avant de le vendre.")
        remove_item(character, item)
        character.coins += item.sell_price
        add_log(character, f"Tu vends {item.name} pour {item.sell_price} écus.")
        character.save()
    return character
