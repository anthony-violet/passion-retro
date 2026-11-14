from django.db import transaction
from django.db.models import F

from .models import UserLevel, xp_required

GOLD_PER_LEVEL = 20


def grant_experience(user, amount):
    """Ajoute de l'expérience à un utilisateur et gère les passages de niveau.

    Le calcul repose sur une expérience cumulée : plusieurs niveaux peuvent être
    franchis d'un seul coup. L'opération est atomique et renvoie le nombre de
    niveaux gagnés.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return 0
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return 0
    if amount <= 0:
        return 0

    with transaction.atomic():
        UserLevel.objects.get_or_create(
            user=user, defaults={'level': 1, 'experience': 0}
        )
        user_level = UserLevel.objects.select_for_update().get(user=user)

        user_level.experience += amount
        levels_gained = 0
        while user_level.experience >= xp_required(user_level.level):
            user_level.level += 1
            levels_gained += 1

        user_level.save(update_fields=['level', 'experience'])

        if levels_gained:
            award_level_rewards(user, user_level.level, levels_gained)

    return levels_gained


def award_level_rewards(user, new_level, levels_gained):
    """Envoie le message et l'or de récompense, sans jamais bloquer le gain d'XP."""
    gold = GOLD_PER_LEVEL * levels_gained
    _send_level_message(user, new_level)
    _add_gold(user, gold)


def _send_level_message(user, new_level):
    from django.contrib.auth import get_user_model

    try:
        from messagerie.models import PrivateMessage, PrivateMessageSubject

        User = get_user_model()
        bot = User.objects.filter(username='RetroBot').first()
        if bot is None:
            return

        subject = PrivateMessageSubject.objects.create(
            receiver=user,
            sender=bot,
            subject=f"Bravo {user} ! Tu as atteint un nouveau niveau !",
        )
        PrivateMessage.objects.create(
            subject=subject,
            author=bot,
            message=(
                f"[b]Félicitations {user} ![/b]\n\n"
                f"Tu viens de passer au [b]Niveau {new_level}[/b] !\n\n"
                f"Continue tes efforts, aventurier, et vise toujours plus haut !"
            ),
        )
    except Exception:
        # Une récompense cosmétique ne doit jamais faire échouer le gain d'XP.
        pass


def _add_gold(user, amount):
    from .models import UserInventory

    inventory_item = UserInventory.objects.filter(
        user=user, item__name='Or'
    ).first()
    if inventory_item is None:
        return
    UserInventory.objects.filter(pk=inventory_item.pk).update(
        quantity=F('quantity') + amount
    )
