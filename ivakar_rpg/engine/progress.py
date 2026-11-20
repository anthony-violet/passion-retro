"""Objectifs : succès (à vie) et tâches quotidiennes (renouvelées chaque jour).

Les deux suivent les mêmes compteurs du héros (``METRICS``). Une tâche du jour retient la valeur de son
compteur au moment du tirage : sa progression est l'écart depuis ce moment. Rien n'est donc à brancher
dans chaque action du jeu, il suffit que les compteurs existent.

PROVISOIRE (voir REGLES.md) : 3 tâches par jour (changement à minuit, heure de Paris), bonus de
journée complète, récompenses versées dès que l'objectif est atteint.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Achievement, CharacterAchievement, CharacterDailyTask, CharacterQuest, DailyTask, Duel,
    EventParticipation, LocationMessage, Trade,
)
from .character import add_log, change_coins, gain_xp, lock
from .dice import get_rng
from .notifications import notify

DAILY_COUNT = 3
DAILY_BONUS_COINS = 15
DAILY_BONUS_XP = 10


def _metric(character, code, flag=''):
    """Valeur actuelle d'un compteur du héros."""
    if code == 'victories':
        return character.victories
    if code == 'explorations':
        return character.explorations
    if code == 'travels':
        return character.travel_count
    if code == 'choices':
        return character.choices_made
    if code == 'locations':
        return len(character.visited or [])
    if code == 'quests':
        return CharacterQuest.objects.filter(character=character, status=CharacterQuest.STATUS_DONE).count()
    if code == 'duels_won':
        return character.duel_wins
    if code == 'duels_fought':
        return Duel.objects.filter(Q(challenger=character) | Q(opponent=character),
                                   status=Duel.STATUS_FINISHED).count()
    if code == 'event_attacks':
        return EventParticipation.objects.filter(character=character).aggregate(n=Sum('attacks'))['n'] or 0
    if code == 'trades':
        return Trade.objects.filter(Q(proposer=character) | Q(receiver=character),
                                    status=Trade.STATUS_ACCEPTED).count()
    if code == 'tavern':
        return LocationMessage.objects.filter(character=character).count()
    if code == 'npcs':
        return len(character.npcs_met or [])
    if code == 'knockouts':
        return character.knockouts
    if code == 'daily_done':
        return character.daily_tasks_done
    if code == 'level':
        return character.level
    if code == 'flag':
        return int(bool(flag) and character.has_flag(flag))
    return 0


class _Metrics:
    """Cache des compteurs le temps d'un calcul (un même compteur sert à plusieurs objectifs)."""

    def __init__(self, character):
        self.character = character
        self.values = {}

    def get(self, code, flag=''):
        key = (code, flag)
        if key not in self.values:
            self.values[key] = _metric(self.character, code, flag)
        return self.values[key]


def _reward(character, xp, coins, reason):
    if coins:
        change_coins(character, coins)
        add_log(character, f"{reason} : +{coins} écus.", 'good')
    if xp:
        add_log(character, f"{reason} : +{xp} XP.", 'good')
        gain_xp(character, xp)


# ---------------------------------------------------------------------------
# Tâches quotidiennes
# ---------------------------------------------------------------------------
def today():
    return timezone.localdate()


def ensure_today(character, rng=None, day=None):
    """Tire les tâches du jour du héros si ce n'est pas encore fait."""
    day = day or today()
    existing = list(CharacterDailyTask.objects.filter(character=character, day=day).select_related('task'))
    if existing:
        return existing
    pool = [t for t in DailyTask.objects.filter(is_active=True, min_level__lte=character.level) if t.weight > 0]
    rng = get_rng(rng)
    picked = []
    while pool and len(picked) < DAILY_COUNT:
        total = sum(t.weight for t in pool)
        roll = rng.randint(1, total)
        for task in pool:
            roll -= task.weight
            if roll <= 0:
                picked.append(task)
                pool.remove(task)
                break
    metrics = _Metrics(character)
    try:
        with transaction.atomic():
            for task in picked:
                CharacterDailyTask.objects.create(character=character, task=task, day=day,
                                                  baseline=metrics.get(task.metric))
    except IntegrityError:  # tirage simultané dans une autre requête : on garde le sien
        pass
    return list(CharacterDailyTask.objects.filter(character=character, day=day).select_related('task'))


def daily_view(character, day=None):
    """Tâches du jour avec leur progression : liste de dicts."""
    metrics = _Metrics(character)
    result = []
    for entry in ensure_today(character, day=day):
        task = entry.task
        done = min(task.goal, max(0, metrics.get(task.metric) - entry.baseline))
        result.append({'entry': entry, 'task': task, 'progress': task.goal if entry.completed_at else done,
                       'percent': 100 if entry.completed_at else int(100 * done / task.goal),
                       'completed': entry.completed_at is not None})
    return result


# ---------------------------------------------------------------------------
# Succès
# ---------------------------------------------------------------------------
def achievements_view(character):
    """Tous les succès actifs avec l'état du héros : liste de dicts."""
    metrics = _Metrics(character)
    unlocked = dict(CharacterAchievement.objects.filter(character=character)
                    .values_list('achievement_id', 'unlocked_at'))
    result = []
    for achievement in Achievement.objects.filter(is_active=True):
        value = metrics.get(achievement.metric, achievement.flag)
        goal = 1 if achievement.metric == 'flag' else achievement.goal
        result.append({
            'achievement': achievement, 'unlocked_at': unlocked.get(achievement.pk),
            'progress': min(goal, value), 'goal': goal, 'percent': int(100 * min(goal, value) / goal),
            'secret': achievement.hidden and achievement.pk not in unlocked,
        })
    return result


# ---------------------------------------------------------------------------
# Mise à jour (appelée à l'affichage des pages du jeu)
# ---------------------------------------------------------------------------
def _pending(character, day):
    """Ce qui vient d'être atteint : (tâches du jour, succès), sans rien modifier."""
    metrics = _Metrics(character)
    tasks = [e for e in CharacterDailyTask.objects.filter(character=character, day=day, completed_at=None)
             .select_related('task') if metrics.get(e.task.metric) - e.baseline >= e.task.goal]
    have = set(CharacterAchievement.objects.filter(character=character).values_list('achievement_id', flat=True))
    achievements = [a for a in Achievement.objects.filter(is_active=True).exclude(pk__in=have)
                    if metrics.get(a.metric, a.flag) >= (1 if a.metric == 'flag' else a.goal)]
    return tasks, achievements


def update(character, now=None):
    """Valide les tâches du jour et les succès atteints, verse les récompenses. Renvoie ``True`` si le héros
    a changé (le relire)."""
    day = timezone.localdate(now) if now else today()
    ensure_today(character, day=day)
    changed = False
    for _ in range(3):  # une récompense peut en débloquer une autre (XP → niveau → succès)
        tasks, achievements = _pending(character, day)
        if not tasks and not achievements:
            break
        changed = True
        with transaction.atomic():
            character = lock(character)
            for entry in tasks:
                if CharacterDailyTask.objects.filter(pk=entry.pk, completed_at=None) \
                        .update(completed_at=now or timezone.now()) == 0:
                    continue  # déjà validée par une autre requête
                character.daily_tasks_done += 1
                task = entry.task
                add_log(character, f"Tâche du jour accomplie : {task.name} !", 'good')
                _reward(character, task.reward_xp, task.reward_coins, "Tâche du jour")
                notify(character, 'daily_done', f"Tâche du jour accomplie : {task.name}",
                       _reward_text(task.reward_xp, task.reward_coins), reverse('rpg_progress'))
            _daily_bonus(character, day)
            unlocked = []
            for achievement in achievements:
                _, created = CharacterAchievement.objects.get_or_create(character=character, achievement=achievement)
                if not created:
                    continue
                unlocked.append(achievement)
                add_log(character, f"Succès débloqué : {achievement.name} !", 'good')
                _reward(character, achievement.reward_xp, achievement.reward_coins, "Succès")
            _notify_achievements(character, unlocked)
            character.save()
    return changed


def _notify_achievements(character, unlocked):
    """Un popup par succès ; au-delà de deux d'un coup (rattrapage d'un héros ancien), un seul popup."""
    url = reverse('rpg_progress')
    if len(unlocked) > 2:
        names = ", ".join(f"{a.icon} {a.name}" for a in unlocked)
        notify(character, 'achievement', f"{len(unlocked)} succès débloqués !", names, url)
        return
    for a in unlocked:
        notify(character, 'achievement', f"{a.icon} Succès : {a.name}",
               f"{a.description} {_reward_text(a.reward_xp, a.reward_coins)}".strip(), url, ref=f"achievement:{a.pk}")


def _daily_bonus(character, day):
    """Toutes les tâches du jour faites : un petit bonus, une fois par jour."""
    if character.daily_bonus_day == day:
        return
    entries = CharacterDailyTask.objects.filter(character=character, day=day)
    if not entries.exists() or entries.filter(completed_at=None).exists():
        return
    character.daily_bonus_day = day
    add_log(character, "Journée complète : toutes tes tâches du jour sont faites !", 'good')
    _reward(character, DAILY_BONUS_XP, DAILY_BONUS_COINS, "Journée complète")
    notify(character, 'daily_all', "Journée complète !", f"Bonus : {_reward_text(DAILY_BONUS_XP, DAILY_BONUS_COINS)}",
           reverse('rpg_progress'), ref=f"daily_all:{day.isoformat()}")


def _reward_text(xp, coins):
    parts = [f"+{xp} XP" if xp else '', f"+{coins} écus" if coins else '']
    return " · ".join(p for p in parts if p)


def counts(character, day=None):
    """Résumé pour la barre latérale : (tâches du jour faites, tâches du jour)."""
    day = day or today()
    entries = CharacterDailyTask.objects.filter(character=character, day=day)
    return entries.exclude(completed_at=None).count(), entries.count()

