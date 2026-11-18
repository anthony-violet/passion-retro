from django.db import transaction
from django.db.models import F

from .models import UserLevel, level_title, xp_required

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
            award_level_rewards(user, user_level.level, levels_gained, user_level.experience)

    return levels_gained


def award_level_rewards(user, new_level, levels_gained, experience=None):
    """Envoie le message et l'or de récompense, sans jamais bloquer le gain d'XP."""
    gold = GOLD_PER_LEVEL * levels_gained
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
    from .models import UserInventory

    inventory_item = UserInventory.objects.filter(
        user=user, item__name='Or'
    ).first()
    if inventory_item is None:
        return False
    UserInventory.objects.filter(pk=inventory_item.pk).update(
        quantity=F('quantity') + amount
    )
    return True
