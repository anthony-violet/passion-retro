"""Échanges entre héros : une proposition (objets + écus contre objets + écus) que l'autre accepte ou refuse.

Rien n'est bloqué pendant l'attente : tout est revérifié au moment de l'acceptation.
"""
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..models import Character, InventoryItem, Item, Trade, TradeLine
from . import RpgError
from .character import add_item, add_log, max_hp, remove_item
from .notifications import notify

MAX_PENDING = 5


def _parse_lines(lines):
    """``lines`` = ``{item_id: quantité}`` -> ``[(Item, quantité)]`` (objets échangeables seulement)."""
    result = []
    for item_id, quantity in (lines or {}).items():
        try:
            item_id, quantity = int(item_id), int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity <= 0:
            continue
        item = Item.objects.filter(pk=item_id).first()
        if item is None:
            continue
        if item.kind == Item.KIND_QUEST:
            raise RpgError(f"{item.name} est un objet de quête : il ne s'échange pas.")
        result.append((item, quantity))
    return result


def _check_owner_has(character, item, quantity):
    entry = InventoryItem.objects.filter(inventory__character=character, item=item).first()
    owned = entry.quantity if entry else 0
    if owned < quantity:
        raise RpgError(f"{character.name} n'a pas {quantity} × {item.name}.")


def propose(proposer, receiver_id, offer=None, request=None, offer_coins=0, request_coins=0, message=''):
    """Crée une proposition. Les deux héros doivent être au même endroit."""
    receiver = Character.objects.filter(pk=receiver_id).first()
    if receiver is None or receiver.pk == proposer.pk:
        raise RpgError("Choisis un autre héros.")
    if receiver.location_id != proposer.location_id:
        raise RpgError(f"{receiver.name} n'est pas ici.")
    try:
        offer_coins, request_coins = max(0, int(offer_coins or 0)), max(0, int(request_coins or 0))
    except (TypeError, ValueError):
        raise RpgError("Montant d'écus invalide.")
    offer, request = _parse_lines(offer), _parse_lines(request)
    if not (offer or request or offer_coins or request_coins):
        raise RpgError("Ton échange est vide.")
    if offer_coins > proposer.coins:
        raise RpgError("Tu n'as pas autant d'écus.")
    for item, quantity in offer:
        _check_owner_has(proposer, item, quantity)
    if Trade.objects.filter(proposer=proposer, status=Trade.STATUS_PENDING).count() >= MAX_PENDING:
        raise RpgError(f"Tu as déjà {MAX_PENDING} propositions en attente.")
    with transaction.atomic():
        trade = Trade.objects.create(proposer=proposer, receiver=receiver, offer_coins=offer_coins,
                                     request_coins=request_coins, message=(message or '')[:200])
        TradeLine.objects.bulk_create(
            [TradeLine(trade=trade, side=TradeLine.SIDE_OFFER, item=i, quantity=q) for i, q in offer]
            + [TradeLine(trade=trade, side=TradeLine.SIDE_REQUEST, item=i, quantity=q) for i, q in request])
        notify(receiver, 'trade_received', f"{proposer.name} te propose un échange.",
               (message or '')[:200], reverse('rpg_trades'))
    return trade


def _locked(trade_id):
    trade = Trade.objects.select_for_update().filter(pk=trade_id).first()
    if trade is None:
        raise RpgError("Cet échange n'existe plus.")
    if trade.status != Trade.STATUS_PENDING:
        raise RpgError("Cet échange n'est plus en attente.")
    return trade


def _transfer(giver, taker, item, quantity):
    """Retire de l'un, donne à l'autre. Un objet équipé dont il ne reste rien est déséquipé d'office."""
    if not remove_item(giver, item, quantity):
        raise RpgError(f"{giver.name} n'a plus {quantity} × {item.name}.")
    add_item(taker, item, quantity)


def accept(receiver, trade_id):
    failure = None
    with transaction.atomic():
        trade = _locked(trade_id)
        if trade.receiver_id != receiver.pk:
            raise RpgError("Cet échange ne t'est pas destiné.")
        # Verrouillage des deux héros dans un ordre fixe pour éviter les interblocages.
        heroes = {c.pk: c for c in Character.objects.select_for_update()
                  .filter(pk__in=[trade.proposer_id, trade.receiver_id]).order_by('pk')}
        proposer, receiver = heroes[trade.proposer_id], heroes[trade.receiver_id]
        try:
            if proposer.coins < trade.offer_coins:
                raise RpgError(f"{proposer.name} n'a plus assez d'écus.")
            if receiver.coins < trade.request_coins:
                raise RpgError("Tu n'as pas assez d'écus.")
            with transaction.atomic():  # point de sauvegarde : un transfert raté annule les précédents
                for line in trade.lines.select_related('item'):
                    if line.side == TradeLine.SIDE_OFFER:
                        _transfer(proposer, receiver, line.item, line.quantity)
                    else:
                        _transfer(receiver, proposer, line.item, line.quantity)
        except RpgError as error:
            failure = error
            trade.status = Trade.STATUS_FAILED
        else:
            proposer.coins += trade.request_coins - trade.offer_coins
            receiver.coins += trade.offer_coins - trade.request_coins
            for hero in (proposer, receiver):
                hero.hp = min(hero.hp, max_hp(hero))  # un objet de PV max a pu changer de mains
            add_log(proposer, f"Échange conclu avec {receiver.name}.", 'good')
            add_log(receiver, f"Échange conclu avec {proposer.name}.", 'good')
            proposer.save()
            receiver.save()
            trade.status = Trade.STATUS_ACCEPTED
        trade.resolved_at = timezone.now()
        trade.save(update_fields=['status', 'resolved_at'])
        if failure:
            notify(proposer, 'trade_failed', f"Ton échange avec {receiver.name} n'a pas pu se faire.", str(failure),
                   reverse('rpg_trades'))
        else:
            notify(proposer, 'trade_accepted', f"{receiver.name} accepte ton échange !", url=reverse('rpg_inventory'))
    if failure:
        raise RpgError(f"Échange impossible : {failure}")
    return trade


def decline(receiver, trade_id):
    return _close(receiver, trade_id, 'receiver_id', Trade.STATUS_DECLINED)


def cancel(proposer, trade_id):
    return _close(proposer, trade_id, 'proposer_id', Trade.STATUS_CANCELLED)


def _close(character, trade_id, field, status):
    with transaction.atomic():
        trade = _locked(trade_id)
        if getattr(trade, field) != character.pk:
            raise RpgError("Cet échange ne te concerne pas.")
        trade.status = status
        trade.resolved_at = timezone.now()
        trade.save(update_fields=['status', 'resolved_at'])
        if status == Trade.STATUS_DECLINED:
            notify(trade.proposer, 'trade_declined', f"{character.name} refuse ton échange.",
                   url=reverse('rpg_trades'))
    return trade
