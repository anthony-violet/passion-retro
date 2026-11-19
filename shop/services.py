"""Achats en boutique et utilisation des objets de l'inventaire."""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Item


class ShopError(Exception):
    """Achat ou utilisation refusé ; le message s'affiche tel quel au membre."""


def purchase(user, item_id):
    """Achète un exemplaire de ``item_id`` pour ``user``.

    Tout se fait dans une transaction : le débit de l'or ne réussit que si le
    solde suffit au moment de l'écriture, et le stock est verrouillé pendant
    l'achat. Renvoie ``(item, prix_payé)`` ou lève ``ShopError``.
    """
    from users.models import User, UserInventory

    now = timezone.now()
    with transaction.atomic():
        item = (Item.objects.select_for_update().select_related('category')
                .filter(pk=item_id).first())
        if item is None or not item.is_on_sale(now):
            raise ShopError("Cet objet n'est pas en vente.")
        if item.is_sold_out:
            raise ShopError(f"{item.name} est épuisé.")

        owned = UserInventory.objects.select_for_update().filter(user=user, item=item).first()
        if owned and not item.is_stackable:
            raise ShopError(f"Tu possèdes déjà {item.name}.")

        price = item.current_price(now)
        debited = User.objects.filter(pk=user.pk, gold__gte=price).update(gold=F('gold') - price)
        if not debited:
            raise ShopError(f"Tu n'as pas assez d'or pour acheter {item.name}.")

        if item.stock is not None:
            item.stock -= 1
            item.save(update_fields=['stock'])

        if owned:
            UserInventory.objects.filter(pk=owned.pk).update(quantity=F('quantity') + 1)
        else:
            UserInventory.objects.create(user=user, item=item, quantity=1, acquired_at=now)

    user.refresh_from_db(fields=['gold'])
    return item, price


def use_item(user, item_id):
    """Équipe/retire un objet, ou consomme un consommable. Renvoie le message à afficher."""
    from users.models import UserInventory

    entry = (UserInventory.objects.select_related('item__category')
             .filter(user=user, item_id=item_id, quantity__gt=0).first())
    if entry is None:
        raise ShopError("Cet objet n'est pas dans ton inventaire.")
    item = entry.item

    if item.is_equippable:
        field = item.equip_field
        if item.is_equipped_by(user):
            setattr(user, field, 'default' if item.kind == Item.KIND_THEME else None)
            message = f"Tu as retiré {item.name}."
        else:
            setattr(user, field, item.slug)
            message = f"Tu as équipé {item.name}."
        user.save(update_fields=[field])
        return message

    if item.effect == Item.EFFECT_XP_BOOST:
        return _consume_xp_boost(user, entry)

    raise ShopError(f"{item.name} est un objet de collection : il ne s'utilise pas.")


def _consume_xp_boost(user, entry):
    from users.models import User, UserInventory

    item = entry.item
    now = timezone.now()
    with transaction.atomic():
        consumed = UserInventory.objects.filter(pk=entry.pk, quantity__gt=0).update(
            quantity=F('quantity') - 1,
        )
        if not consumed:
            raise ShopError("Cet objet n'est pas dans ton inventaire.")
        UserInventory.objects.filter(pk=entry.pk, quantity=0).delete()

        locked = User.objects.select_for_update().get(pk=user.pk)
        start = max(now, locked.xp_boost_until or now)
        locked.xp_boost_until = start + timedelta(hours=item.effect_hours)
        locked.save(update_fields=['xp_boost_until'])

    user.xp_boost_until = locked.xp_boost_until
    until = timezone.localtime(locked.xp_boost_until)
    return f"Boost d'XP x2 activé jusqu'au {until:%d/%m à %H:%M} !"


def equipped_items(user, entries):
    """Pour chaque emplacement équipable, l'entrée d'inventaire équipée (ou None)."""
    slots = {kind: None for kind in Item.EQUIP_FIELDS}
    for entry in entries:
        if entry.item.is_equippable and entry.item.is_equipped_by(user):
            slots[entry.item.kind] = entry
    return slots
