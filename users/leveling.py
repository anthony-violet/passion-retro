from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import UserLevel, level_title, xp_required

# Or offert à l'ouverture de l'inventaire.
STARTING_GOLD = 100
# Or gagné en atteignant le niveau N : GOLD_LEVEL_BASE + GOLD_LEVEL_STEP * N.
# La récompense grandit avec le niveau pour suivre le coût en XP, qui lui
# augmente avec le carré du niveau.
GOLD_LEVEL_BASE = 10
GOLD_LEVEL_STEP = 2


# Or gagné pour une action communautaire, en plus de l'XP.
GOLD_SMALL_ACTION = 1  # réponse, réaction, commentaire, contribution
GOLD_BIG_ACTION = 2    # nouveau sujet, article, actu ou souvenir publié


def gold_for_level(level):
    """Or offert pour avoir atteint le niveau ``level``."""
    return GOLD_LEVEL_BASE + GOLD_LEVEL_STEP * level


def gold_for_levels(new_level, levels_gained=1):
    """Or total pour les ``levels_gained`` niveaux franchis jusqu'à ``new_level``."""
    first = new_level - levels_gained + 1
    return sum(gold_for_level(level) for level in range(max(2, first), new_level + 1))


def xp_multiplier(user, now=None):
    """x2 tant que le membre profite d'un boost d'XP de la boutique."""
    from .models import User

    now = now or timezone.now()
    return 2 if User.objects.filter(pk=user.pk, xp_boost_until__gt=now).exists() else 1


def grant_experience(user, amount, gold=0, boost=True):
    """Ajoute de l'expérience à un utilisateur et gère les passages de niveau.

    ``gold`` crédite en plus des pièces d'or pour l'action récompensée.
    ``boost`` applique le boost d'XP de la boutique s'il est actif (les
    récompenses du staff passent ``boost=False`` : le montant est voulu).

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
    if boost:
        amount *= xp_multiplier(user)

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

        if gold > 0:
            _add_gold(user, gold)

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


def grant_starting_gold(user):
    """Offre l'or de départ, une seule fois par membre. Renvoie True s'il vient d'être offert."""
    from .models import User

    given = User.objects.filter(pk=user.pk, starting_gold_given=False).update(
        gold=F('gold') + STARTING_GOLD, starting_gold_given=True,
    )
    user.refresh_from_db(fields=['gold', 'starting_gold_given'])
    return bool(given)


def _add_gold(user, amount):
    """Crédite ``amount`` pièces d'or sur le solde du membre.

    Un membre qui n'a pas encore reçu l'or de départ le reçoit en plus : sinon il
    le perdrait en ouvrant son inventaire plus tard.
    """
    from .models import User

    amount = int(amount or 0)
    if amount <= 0:
        return False
    User.objects.filter(pk=user.pk, starting_gold_given=False).update(
        gold=F('gold') + STARTING_GOLD, starting_gold_given=True,
    )
    User.objects.filter(pk=user.pk).update(gold=F('gold') + amount)
    user.refresh_from_db(fields=['gold', 'starting_gold_given'])
    return True
