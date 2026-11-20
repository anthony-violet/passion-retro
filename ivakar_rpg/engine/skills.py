"""Compétences : actions de combat propres à une origine, débloquées au niveau requis.

Une compétence se joue comme une action (code ``skill:<slug>``) en combat comme en duel. Après usage,
elle reste indisponible pendant ``cooldown`` manches. Les règles de résolution sont dans ``clash``.

PROVISOIRE (voir REGLES.md) : obtention automatique au niveau requis, recharge en manches, effets
construits à partir d'un type d'action de base.
"""
from django.urls import reverse

from ..models import Skill
from . import RpgError
from .clash import GUARD, SHAKEN_ALLOWED, SKILL_BASE

PREFIX = 'skill:'


def known(character):
    """Compétences du héros : celles de son origine, à son niveau."""
    if not character.origin_id:
        return Skill.objects.none()
    return Skill.objects.filter(is_active=True, origins=character.origin_id, min_level__lte=character.level)


def upcoming(character):
    if not character.origin_id:
        return Skill.objects.none()
    return Skill.objects.filter(is_active=True, origins=character.origin_id, min_level__gt=character.level)


def is_skill(code):
    return bool(code) and code.startswith(PREFIX)


def slug_of(code):
    return code[len(PREFIX):] if is_skill(code) else ''


def usable(character, code, cooldowns, shaken=False):
    """La compétence demandée, si le héros peut l'utiliser maintenant ; sinon ``RpgError``."""
    skill = known(character).filter(slug=slug_of(code)).first()
    if skill is None:
        raise RpgError("Tu ne maîtrises pas cette compétence.")
    wait = (cooldowns or {}).get(skill.slug, 0)
    if wait:
        raise RpgError(f"{skill.name} se recharge encore ({wait} manche{'s' if wait > 1 else ''}).")
    if shaken and SKILL_BASE[skill.kind] not in SHAKEN_ALLOWED:
        raise RpgError("Ébranlé, tu ne peux que frapper ou te garder à cette manche.")
    return skill


def skill_for(code):
    """La compétence d'un code d'action (sans contrôle), ou ``None``."""
    return Skill.objects.filter(slug=slug_of(code)).first() if is_skill(code) else None


def tick(cooldowns, used=None):
    """Recharges après une manche : chacune perd une manche ; la compétence utilisée repart à zéro."""
    result = {slug: left - 1 for slug, left in (cooldowns or {}).items() if left > 1}
    if used is not None and used.cooldown:
        result[used.slug] = used.cooldown
    return result


def menu(character, cooldowns, shaken=False):
    """Compétences à afficher dans un combat : liste de dicts."""
    entries = []
    for skill in known(character):
        wait = (cooldowns or {}).get(skill.slug, 0)
        blocked = shaken and SKILL_BASE[skill.kind] not in SHAKEN_ALLOWED
        entries.append({'skill': skill, 'code': skill.code, 'wait': wait, 'ready': not wait and not blocked,
                        'is_guard': SKILL_BASE[skill.kind] == GUARD})
    return entries


def label(code):
    """Libellé d'une action ou d'une compétence."""
    from .clash import ACTIONS, action_label

    if code in ACTIONS:
        return action_label(code)
    skill = skill_for(code)
    return f"{skill.icon} {skill.name}" if skill else code


def notify_learned(character, old_level):
    """Prévient le héros des compétences débloquées par ses nouveaux niveaux."""
    from .notifications import notify

    if not character.origin_id:
        return
    for skill in Skill.objects.filter(is_active=True, origins=character.origin_id, min_level__gt=old_level,
                                      min_level__lte=character.level):
        notify(character, 'skill_learned', f"{skill.icon} Nouvelle compétence : {skill.name}",
               skill.description, reverse('rpg_sheet'), ref=f"skill:{skill.pk}")
