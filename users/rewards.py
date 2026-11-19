"""Récompenses attribuées à la main par l'équipe (concours, événements…)."""
from django.conf import settings
from django.db import transaction

from .leveling import _add_gold, grant_experience
from .models import StaffReward, UserInventory


def give_reward(user, given_by, reason, experience=0, gold=0, item=None, notify=True):
    """Crédite XP, or et/ou objet à ``user`` et garde une trace de l'attribution.

    Un objet déjà possédé n'est pas redonné (la boutique ne gère qu'un exemplaire
    par membre). Renvoie la ``StaffReward`` créée, ou ``None`` si rien n'a été
    donné.
    """
    experience = max(0, int(experience or 0))
    gold = max(0, int(gold or 0))

    with transaction.atomic():
        item_given = None
        if item is not None:
            _, created = UserInventory.objects.get_or_create(
                user=user, item=item, defaults={'quantity': 1},
            )
            if created:
                item_given = item

        gold_given = gold if gold and _add_gold(user, gold) else 0

        if not (experience or gold_given or item_given):
            return None

        reward = StaffReward.objects.create(
            user=user, given_by=given_by, reason=reason,
            experience=experience, gold=gold_given, item=item_given,
        )

    # Hors transaction : un passage de niveau envoie son propre message.
    if experience:
        grant_experience(user, experience, boost=False)
    if notify:
        _notify(reward)
    return reward


def reward_message(reward):
    gains = []
    if reward.experience:
        gains.append(f"[b]{reward.experience} XP[/b]")
    if reward.gold:
        gains.append(f"[b]{reward.gold} pièce{'s' if reward.gold > 1 else ''} d'or[/b]")
    if reward.item:
        gains.append(f"l'objet [b]{reward.item.name}[/b]")
    if len(gains) > 1:
        gains_text = ", ".join(gains[:-1]) + " et " + gains[-1]
    else:
        gains_text = gains[0]

    subject = f"🎁 Une récompense pour toi : {reward.reason}"
    lines = [
        f"Hé {reward.user} ! 👋",
        f"L'équipe de {settings.SITE_NAME} t'offre {gains_text} pour : [b]{reward.reason}[/b].",
    ]
    if reward.gold or reward.item:
        lines.append("Tout est déjà rangé dans ton inventaire. 😉")
    lines.append("Bravo et merci de faire vivre la communauté !")
    lines.append("RetroBot 🤖\n[i]Message envoyé automatiquement, inutile d'y répondre.[/i]")
    return subject, "\n\n".join(lines)


def _notify(reward):
    from django.utils.text import Truncator

    from messagerie.models import PrivateMessage, PrivateMessageSubject
    from .models import User

    try:
        sender = User.objects.filter(username='RetroBot').first() or reward.given_by
        if sender is None:
            return
        subject, body = reward_message(reward)
        thread = PrivateMessageSubject.objects.create(
            receiver=reward.user, sender=sender, subject=Truncator(subject).chars(100),
        )
        PrivateMessage.objects.create(subject=thread, author=sender, message=body)
    except Exception:
        # Le message est un bonus : il ne doit pas annuler la récompense.
        pass
