"""Événements de serveur : une menace commune que tous les héros affaiblissent, chacun à son rythme.

Validé : chaque jet est 2D6 + ⌊caractéristique ÷ 3⌋ ; 0 PV mène au KO (et non à la mort), comme partout.

PROVISOIRE (voir REGLES.md) : l'assaut et l'esquive de la riposte sont des oppositions Dextérité du héros
contre Dextérité de la menace (égalité : avantage au défenseur) ; délai entre deux assauts, dégâts
(1D6 + ⌊Force ÷ 3⌋ + arme), riposte après chaque assaut, récompenses (XP et écus pour tout participant,
un objet pour le meilleur).
"""
from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..models import Character, EventParticipation, WorldEvent
from . import RpgError
from .character import add_item, add_log, change_coins, gain_xp, lock, sheet
from .dice import get_rng
from .notifications import notify
from .rules import bonus

LOG_SIZE = 20


def active_events(now=None):
    now = now or timezone.now()
    return WorldEvent.objects.filter(starts_at__lte=now, ends_at__gt=now, hp_left__gt=0) \
        .select_related('location', 'monster')


def current_event(now=None):
    return active_events(now).first()


def status(event, now=None):
    now = now or timezone.now()
    if event.hp_left == 0:
        return 'won'
    if now < event.starts_at:
        return 'upcoming'
    if now >= event.ends_at:
        return 'failed'
    return 'active'


def _log(event, text):
    event.log = (list(event.log or []) + [{'text': text, 'at': timezone.now().isoformat()}])[-LOG_SIZE:]


def next_attack_at(event, character):
    participation = EventParticipation.objects.filter(event=event, character=character).first()
    if participation is None or participation.last_attack_at is None:
        return None
    return participation.last_attack_at + timedelta(minutes=event.cooldown_minutes)


def _roll(value, rng):
    dice = (rng.randint(1, 6), rng.randint(1, 6))
    return sum(dice) + bonus(value), f"2D6 ({dice[0]}+{dice[1]}) + ⌊{value} ÷ 3⌋ ({bonus(value)})"


def _oppose(character, label, hero_value, threat_value, rng, hero_attacks):
    """Opposition entre le héros et la menace ; renvoie ``True`` si le héros l'emporte."""
    hero_total, hero_detail = _roll(hero_value, rng)
    threat_total, _ = _roll(threat_value, rng)
    success = hero_total > threat_total if hero_attacks else hero_total >= threat_total
    add_log(character, f"{label} : {hero_detail} = {hero_total} contre {threat_total}"
                       f"{' — réussite' if success else ' — échec'}.", 'good' if success else 'bad')
    return success


def attack(character, event_id, rng=None, now=None):
    """Un assaut contre la menace, puis sa riposte (si elle tient encore debout)."""
    from .wounds import knock_out

    rng = get_rng(rng)
    now = now or timezone.now()
    with transaction.atomic():
        event = WorldEvent.objects.select_for_update().filter(pk=event_id).first()
        if event is None or status(event, now) != 'active':
            raise RpgError("Cet événement n'est pas en cours.")
        character = lock(character)
        if character.is_ko:
            raise RpgError("Tu es inconscient.")
        if event.location_id and character.location_id != event.location_id:
            raise RpgError(f"La menace se trouve à {event.location.name} : il faut t'y rendre.")
        participation, _ = EventParticipation.objects.select_for_update().get_or_create(event=event,
                                                                                         character=character)
        if participation.last_attack_at and now < participation.last_attack_at + timedelta(
                minutes=event.cooldown_minutes):
            raise RpgError("Tu reprends ton souffle : ton prochain assaut n'est pas encore possible.")

        stats = sheet(character)
        participation.attacks += 1
        participation.last_attack_at = now
        if _oppose(character, f"Assaut contre {event.name} (Dextérité)", stats['dexterity'], event.dexterite, rng,
                   hero_attacks=True):
            damage = max(1, rng.randint(1, 6) + stats['damage_bonus'])
            damage = min(damage, event.hp_left)
            event.hp_left -= damage
            participation.damage += damage
            add_log(character, f"Tu infliges {damage} dégâts à {event.name}.", 'good')
            _log(event, f"{character.name} inflige {damage} dégâts.")
        participation.save()

        if event.hp_left == 0:
            _log(event, f"{character.name} porte le coup décisif : {event.name} est vaincu !")
            add_log(character, f"Coup décisif ! {event.name} est vaincu.", 'good')
            character.save()
            event.save()
            distribute_rewards(event)
            return event

        if not _oppose(character, "Esquive de la riposte (Dextérité)", stats['dexterity'], event.dexterite, rng,
                       hero_attacks=False):
            hit = max(1, rng.randint(event.damage_min, max(event.damage_min, event.damage_max)) - stats['armor'])
            character.hp = max(0, character.hp - hit)
            add_log(character, f"{event.name} riposte : −{hit} PV.", 'bad')
            if character.hp == 0:
                _log(event, f"{character.name} tombe face à {event.name}.")
                knock_out(character, rng)
        character.save()
        event.save()
    return event


def distribute_rewards(event):
    """Récompense chaque participant ayant porté au moins un coup (une seule fois)."""
    if event.rewards_given or event.hp_left > 0:
        return
    participations = list(EventParticipation.objects.select_for_update().filter(event=event, damage__gt=0,
                                                                                 rewarded=False).order_by('-damage'))
    best = participations[0] if participations else None
    for participation in participations:
        character = lock(participation.character)
        add_log(character, f"{event.name} est vaincu grâce à toi et aux autres héros !", 'good')
        notify(character, 'event_won', f"{event.name} est vaincu !",
               f"Tu as infligé {participation.damage} dégâts. Tes récompenses t'attendent.",
               reverse('rpg_event_detail', args=[event.pk]), ref=f"event_won:{event.pk}")
        if event.reward_coins:
            change_coins(character, event.reward_coins)
            add_log(character, f"Récompense : +{event.reward_coins} écus.", 'good')
        if participation is best and event.top_reward_item_id:
            add_item(character, event.top_reward_item)
            add_log(character, f"Meilleur participant ! Tu reçois {event.top_reward_item.name}.", 'good')
        if event.reward_xp:
            add_log(character, f"Récompense : +{event.reward_xp} XP.", 'good')
            gain_xp(character, event.reward_xp)
        character.save()
        participation.rewarded = True
        participation.save(update_fields=['rewarded'])
    event.rewards_given = True
    event.save(update_fields=['rewards_given'])


def ranking(event, limit=10):
    return EventParticipation.objects.filter(event=event, damage__gt=0).select_related('character__user')[:limit]
