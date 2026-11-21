"""Groupes de héros : invitations, discussion de groupe, appel à l'aide en combat.

Un groupe compte au plus ``Party.MAX_SIZE`` héros. Chacun voyage librement : le groupe sert à discuter
d'où qu'on soit et à se battre ensemble quand on se trouve au même endroit (voir ``combat``).
Inviter quelqu'un sans avoir de groupe en fonde un, dont on devient le chef. Seul le chef invite et
exclut ; s'il part, le plus ancien membre prend sa place. Un groupe réduit à un héros sans invitation
en attente est dissous.
"""
from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..models import Character, Party, PartyInvite, PartyMember, PartyMessage
from . import RpgError
from .notifications import notify

MESSAGE_MAX_LENGTH = 300
MESSAGE_COOLDOWN_SECONDS = 3
CHAT_SIZE = 40


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------
def party_of(character):
    """Groupe du héros, ou ``None``."""
    membership = PartyMember.objects.select_related('party__leader').filter(character=character).first()
    return membership.party if membership else None


def members(party):
    """Héros du groupe, du plus ancien au plus récent."""
    if party is None:
        return []
    return [m.character for m in party.members.select_related('character__location')]


def member_ids(party):
    return list(party.members.values_list('character_id', flat=True)) if party else []


def mates(character):
    """Les autres membres du groupe du héros."""
    return [m for m in members(party_of(character)) if m.pk != character.pk]


def invites_for(character):
    return PartyInvite.objects.filter(character=character).select_related('party__leader', 'invited_by')


def _url():
    return reverse('rpg_party')


def _tell(party, kind, title, body='', exclude=None, url=None):
    for mate in members(party):
        if exclude is None or mate.pk != exclude.pk:
            notify(mate, kind, title, body, url or _url())


def _locked_party(party_id):
    party = Party.objects.select_for_update().select_related('leader').filter(pk=party_id).first()
    if party is None:
        raise RpgError("Ce groupe n'existe plus.")
    return party


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------
def invite(character, target_id):
    """Invite un héros présent dans le même lieu ; fonde le groupe si besoin."""
    target = Character.objects.filter(pk=target_id).first()
    if target is None or target.pk == character.pk:
        raise RpgError("Choisis un autre héros.")
    if target.location_id != character.location_id:
        raise RpgError(f"{target.name} n'est pas ici : pour l'inviter, rejoins-le.")
    with transaction.atomic():
        party = party_of(character)
        if party is None:
            party = Party.objects.create(leader=character)
            PartyMember.objects.create(party=party, character=character)
        party = _locked_party(party.pk)
        if party.leader_id != character.pk:
            raise RpgError(f"Seul le chef du groupe, {party.leader.name}, peut inviter.")
        if PartyMember.objects.filter(character=target).exists():
            raise RpgError(f"{target.name} fait déjà partie d'un groupe.")
        if PartyInvite.objects.filter(party=party, character=target).exists():
            raise RpgError(f"{target.name} a déjà une invitation de ta part.")
        if party.members.count() + party.invites.count() >= Party.MAX_SIZE:
            raise RpgError(f"Un groupe compte au plus {Party.MAX_SIZE} héros (invitations comprises).")
        PartyInvite.objects.create(party=party, character=target, invited_by=character)
    notify(target, 'party_invite', f"{character.name} t'invite dans son groupe !",
           "Discutez ensemble et combattez côte à côte.", _url())
    return party


def accept(character, invite_id):
    with transaction.atomic():
        invitation = PartyInvite.objects.select_related('party').filter(pk=invite_id, character=character).first()
        if invitation is None:
            raise RpgError("Cette invitation n'existe plus.")
        party = _locked_party(invitation.party_id)
        if PartyMember.objects.filter(character=character).exists():
            raise RpgError("Quitte d'abord ton groupe actuel.")
        if party.members.count() >= Party.MAX_SIZE:
            raise RpgError("Ce groupe est déjà complet.")
        PartyMember.objects.create(party=party, character=character)
        PartyInvite.objects.filter(character=character).delete()
    _tell(party, 'party_joined', f"{character.name} rejoint le groupe !", exclude=character)
    return party


def decline(character, invite_id):
    with transaction.atomic():
        invitation = PartyInvite.objects.select_related('party').filter(pk=invite_id, character=character).first()
        if invitation is None:
            raise RpgError("Cette invitation n'existe plus.")
        party = _locked_party(invitation.party_id)
        invitation.delete()
        notify(party.leader, 'party_declined', f"{character.name} décline ton invitation.", url=_url())
        _dissolve_if_alone(party)


def cancel_invite(character, invite_id):
    with transaction.atomic():
        invitation = PartyInvite.objects.select_related('party').filter(pk=invite_id).first()
        if invitation is None or invitation.party.leader_id != character.pk:
            raise RpgError("Cette invitation ne te concerne pas.")
        party = _locked_party(invitation.party_id)
        invitation.delete()
        _dissolve_if_alone(party)


# ---------------------------------------------------------------------------
# Départs
# ---------------------------------------------------------------------------
def leave(character):
    with transaction.atomic():
        party = party_of(character)
        if party is None:
            raise RpgError("Tu n'as pas de groupe.")
        party = _locked_party(party.pk)
        PartyMember.objects.filter(party=party, character=character).delete()
        _after_departure(party, character, f"{character.name} quitte le groupe.")


def kick(character, target_id):
    with transaction.atomic():
        party = party_of(character)
        if party is None:
            raise RpgError("Tu n'as pas de groupe.")
        party = _locked_party(party.pk)
        if party.leader_id != character.pk:
            raise RpgError("Seul le chef du groupe peut exclure un membre.")
        membership = PartyMember.objects.select_related('character').filter(party=party, character_id=target_id) \
            .exclude(character=character).first()
        if membership is None:
            raise RpgError("Ce héros n'est pas dans ton groupe.")
        target = membership.character
        membership.delete()
        notify(target, 'party_kicked', f"{character.name} t'a retiré du groupe.", url=_url())
        _after_departure(party, target, f"{target.name} a été retiré du groupe.")


def promote(character, target_id):
    with transaction.atomic():
        party = party_of(character)
        if party is None or party.leader_id != character.pk:
            raise RpgError("Seul le chef du groupe peut passer la main.")
        party = _locked_party(party.pk)
        membership = party.members.select_related('character').filter(character_id=target_id).first()
        if membership is None or membership.character_id == character.pk:
            raise RpgError("Choisis un autre membre du groupe.")
        party.leader = membership.character
        party.save(update_fields=['leader'])
        PartyInvite.objects.filter(party=party).update(invited_by=membership.character)
    _tell(party, 'party_joined', f"{membership.character.name} est le nouveau chef du groupe.", exclude=character)


def _after_departure(party, gone, message):
    remaining = list(party.members.select_related('character'))
    if not remaining:
        party.delete()
        return
    if party.leader_id == gone.pk:
        party.leader = remaining[0].character
        party.save(update_fields=['leader'])
        PartyInvite.objects.filter(party=party).update(invited_by=party.leader)
        message += f" {party.leader.name} prend la tête du groupe."
    if not _dissolve_if_alone(party):
        _tell(party, 'party_left', message)


def _dissolve_if_alone(party):
    """Dissout un groupe réduit à un seul héros sans invitation en attente. Renvoie ``True`` s'il l'est."""
    remaining = list(party.members.select_related('character'))
    if len(remaining) > 1 or party.invites.exists():
        return False
    for membership in remaining:
        notify(membership.character, 'party_left', "Ton groupe est dissous : tu es seul.", url=_url())
    party.delete()
    return True


# ---------------------------------------------------------------------------
# Discussion
# ---------------------------------------------------------------------------
def chat(party, after_id=None):
    """Derniers messages du groupe, du plus ancien au plus récent."""
    if party is None:
        return []
    messages = PartyMessage.objects.filter(party=party).select_related('character')
    if after_id:
        messages = messages.filter(pk__gt=after_id)
    return list(reversed(messages[:CHAT_SIZE]))


def say(character, text, now=None):
    now = now or timezone.now()
    text = ' '.join((text or '').split())
    if not text:
        raise RpgError("Ton message est vide.")
    if len(text) > MESSAGE_MAX_LENGTH:
        raise RpgError(f"Ton message dépasse {MESSAGE_MAX_LENGTH} caractères.")
    party = party_of(character)
    if party is None:
        raise RpgError("Tu n'as pas de groupe.")
    if PartyMessage.objects.filter(character=character,
                                   created_at__gte=now - timedelta(seconds=MESSAGE_COOLDOWN_SECONDS)).exists():
        raise RpgError("Doucement : attends quelques secondes avant de reparler.")
    return PartyMessage.objects.create(party=party, character=character, text=text)


def call_for_help(character, monster):
    """Prévient les membres du groupe présents dans le lieu que le héros vient d'engager un combat."""
    for mate in mates(character):
        if mate.location_id == character.location_id and not mate.is_ko:
            notify(mate, 'party_help', f"{character.name} affronte {monster.name} !",
                   "Tu es tout près : rejoins le combat depuis la page de jeu.", reverse('rpg_play'))
