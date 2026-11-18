from django.db import transaction
from django.db.models import F

from .models import UserLevel, level_title, xp_required

# Or offert à l'ouverture de l'inventaire.
STARTING_GOLD = 100
# Or gagné en atteignant le niveau N : GOLD_LEVEL_BASE + GOLD_LEVEL_STEP * N.
# La récompense grandit avec le niveau pour suivre le coût en XP, qui lui
# augmente avec le carré du niveau.
GOLD_LEVEL_BASE = 10
GOLD_LEVEL_STEP = 2


def gold_for_level(level):
    """Or offert pour avoir atteint le niveau ``level``."""
    return GOLD_LEVEL_BASE + GOLD_LEVEL_STEP * level


def gold_for_levels(new_level, levels_gained=1):
    """Or total pour les ``levels_gained`` niveaux franchis jusqu'à ``new_level``."""
    first = new_level - levels_gained + 1
    return sum(gold_for_level(level) for level in range(max(2, first), new_level + 1))


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
            award_level_rewards(user, user_level.level, levels_gained, user_level.experience)

    return levels_gained


def award_level_rewards(user, new_level, levels_gained, experience=None):
    """Envoie le message et l'or de récompense, sans jamais bloquer le gain d'XP."""
    gold = gold_for_levels(new_level, levels_gained)
    gold_added = _add_gold(user, gold)
    _send_level_message(
        user, new_level,
        levels_gained=levels_gained,
        gold=gold if gold_added else 0,
        experience=experience,
    )


def level_up_message(user, new_level, levels_gained=1, gold=0, experience=None):
    """(sujet, message BBCode) envoyés par RetroBot lors d'un passage de niveau."""
    title = level_title(new_level)
    new_title = title != level_title(new_level - levels_gained)

    subject = f"🎉 Niveau {new_level} débloqué, {user} !"
    if len(subject) > 100:  # longueur max du sujet d'un message privé
        subject = f"🎉 Niveau {new_level} débloqué !"
    lines = [
        f"Hé {user} ! 👋",
        f"Bip bip… mes capteurs viennent de détecter un truc énorme : tu passes au [b]niveau {new_level}[/b] !",
    ]
    if levels_gained > 1:
        lines.append(f"Et tu as même grimpé [b]{levels_gained} niveaux d'un coup[/b]. Rien que ça !")
    if new_title:
        lines.append(f"Nouveau titre débloqué : te voilà [b]{title}[/b]. Ça en jette !")
    if gold:
        lines.append(f"Pour fêter ça, j'ai glissé [b]{gold} pièces d'or[/b] dans ton inventaire. "
                     "À dépenser sans modération à la boutique 😉")
    if experience is not None:
        remaining = max(0, xp_required(new_level) - experience)
        lines.append(f"Prochaine étape : le niveau {new_level + 1}, encore [b]{remaining} XP[/b]. "
                     "Commenter une actu, répondre sur le forum, jouer à un quiz… tout compte !")
    lines.append("Merci de faire vivre la communauté. À très vite par ici !")
    lines.append("RetroBot 🤖\n[i]Message envoyé automatiquement, inutile d'y répondre.[/i]")
    return subject, "\n\n".join(lines)


def _send_level_message(user, new_level, levels_gained=1, gold=0, experience=None):
    from django.contrib.auth import get_user_model

    try:
        from messagerie.models import PrivateMessage, PrivateMessageSubject

        User = get_user_model()
        bot = User.objects.filter(username='RetroBot').first()
        if bot is None:
            return

        subject_text, body = level_up_message(user, new_level, levels_gained, gold, experience)
        subject = PrivateMessageSubject.objects.create(
            receiver=user,
            sender=bot,
            subject=subject_text,
        )
        PrivateMessage.objects.create(subject=subject, author=bot, message=body)
    except Exception:
        # Une récompense cosmétique ne doit jamais faire échouer le gain d'XP.
        pass


def _add_gold(user, amount):
    """Crédite ``amount`` pièces d'or.

    Si l'utilisateur n'a pas encore d'or dans son inventaire, l'entrée est créée
    avec l'or de départ en plus : sinon la récompense serait perdue.
    """
    from shop.models import Item

    from .models import UserInventory

    gold_item = Item.objects.filter(name='Or').first()
    if gold_item is None:
        return False
    inventory_item, created = UserInventory.objects.get_or_create(
        user=user, item=gold_item,
        defaults={'quantity': STARTING_GOLD + amount},
    )
    if not created:
        UserInventory.objects.filter(pk=inventory_item.pk).update(
            quantity=F('quantity') + amount
        )
    return True
