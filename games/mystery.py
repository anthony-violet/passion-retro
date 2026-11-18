"""Règles du jeu mystère : validation des réponses, indices, récompenses et séries."""

import difflib
import re
import unicodedata
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from users.leveling import GOLD_BIG_ACTION, grant_experience

from .models import MysteryAttempt, MysteryClue, MysteryGame

# Récompense quand le jeu est trouvé : elle baisse à chaque indice dévoilé.
# Trouver au 1er indice d'un jeu à 6 indices rapporte 35 XP et 6 or,
# au dernier indice 10 XP et 1 or.
XP_BASE = 10
XP_PER_CLUE_LEFT = 5
GOLD_BASE = 1
GOLD_PER_CLUE_LEFT = 1

# Seuil de ressemblance pour pardonner une faute de frappe.
FUZZY_RATIO = 0.88
FUZZY_MIN_LENGTH = 5
MAX_GUESS_LENGTH = 155

_LEADING_ARTICLES = ('the ', 'le ', 'la ', 'les ', 'l ')
_ROMAN_NUMERALS = {
    'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6',
    'vii': '7', 'viii': '8', 'ix': '9', 'x': '10',
}


def normalize(text):
    """Forme comparable d'un titre : sans accents, ponctuation ni article de tête."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace('&', ' and ')
    text = re.sub(r"[^a-z0-9]+", ' ', text).strip()
    for article in _LEADING_ARTICLES:
        if text.startswith(article):
            text = text[len(article):]
            break
    words = [_ROMAN_NUMERALS.get(word, word) for word in text.split()]
    return ' '.join(words)


def _numbers(normalized):
    return re.findall(r'\d+', normalized)


def is_correct(guess, game):
    candidate = normalize(guess)
    if not candidate:
        return False
    for answer in game.accepted_answers():
        expected = normalize(answer)
        if not expected:
            continue
        if candidate == expected or candidate.replace(' ', '') == expected.replace(' ', ''):
            return True
        # La faute de frappe est tolérée, pas le mauvais numéro : « Final
        # Fantasy VI » ne doit pas valider « Final Fantasy VII ».
        if (len(expected) >= FUZZY_MIN_LENGTH
                and _numbers(candidate) == _numbers(expected)
                and difflib.SequenceMatcher(None, candidate, expected).ratio() >= FUZZY_RATIO):
            return True
    return False


def rewards_for(clues_revealed, clues_total):
    """(xp, or) gagnés en trouvant le jeu après ``clues_revealed`` indices."""
    left = max(0, clues_total - clues_revealed)
    return XP_BASE + XP_PER_CLUE_LEFT * left, GOLD_BASE + GOLD_PER_CLUE_LEFT * left


def today_game():
    return (MysteryGame.objects.filter(publish_date=timezone.localdate(),
                                       status=MysteryGame.STATUS_APPROVED)
            .select_related('author').prefetch_related('clues').first())


def is_author(user, game):
    """L'auteur connaît la réponse : il ne peut pas jouer son propre jeu."""
    return bool(user.is_authenticated and game.author_id == user.pk)


def _locked_attempt(user, game):
    MysteryAttempt.objects.get_or_create(user=user, game=game)
    return MysteryAttempt.objects.select_for_update().get(user=user, game=game)


def _finish(attempt, status):
    attempt.status = status
    attempt.finished = timezone.now()


def guess(user, game, text):
    """Enregistre une proposition. Renvoie (attempt, correct).

    Toute la partie se joue côté serveur : un indice n'est envoyé au navigateur
    qu'une fois dévoilé. Une mauvaise réponse dévoile l'indice suivant ; une
    mauvaise réponse au dernier indice termine la partie.
    """
    text = (text or '').strip()[:MAX_GUESS_LENGTH]
    total = game.clues.count()
    with transaction.atomic():
        attempt = _locked_attempt(user, game)
        if attempt.is_over or not text:
            return attempt, False

        attempt.guesses = attempt.guesses + [text]
        correct = is_correct(text, game)
        if correct:
            xp, gold = rewards_for(attempt.clues_revealed, total)
            attempt.xp_earned, attempt.gold_earned = xp, gold
            _finish(attempt, MysteryAttempt.STATUS_WON)
        elif attempt.clues_revealed >= total:
            _finish(attempt, MysteryAttempt.STATUS_LOST)
        else:
            attempt.clues_revealed += 1
        attempt.save()

        if correct:
            grant_experience(user, attempt.xp_earned, gold=attempt.gold_earned)
    return attempt, correct


def reveal_next_clue(user, game):
    total = game.clues.count()
    with transaction.atomic():
        attempt = _locked_attempt(user, game)
        if not attempt.is_over and attempt.clues_revealed < total:
            attempt.clues_revealed += 1
            attempt.save(update_fields=['clues_revealed'])
    return attempt


def give_up(user, game):
    with transaction.atomic():
        attempt = _locked_attempt(user, game)
        if not attempt.is_over:
            _finish(attempt, MysteryAttempt.STATUS_LOST)
            attempt.save(update_fields=['status', 'finished'])
    return attempt


def streak(user):
    """Nombre de jeux du jour trouvés d'affilée, jusqu'à aujourd'hui (ou hier).

    Un jour sans jeu publié ne casse pas la série.
    """
    today = timezone.localdate()
    games = (MysteryGame.objects.filter(publish_date__isnull=False, publish_date__lte=today)
             .order_by('-publish_date').values_list('id', 'publish_date'))
    won = set(MysteryAttempt.objects.filter(user=user, status=MysteryAttempt.STATUS_WON)
              .values_list('game_id', flat=True))
    count = 0
    for game_id, day in games:
        if game_id in won:
            count += 1
        elif day == today:
            continue  # la partie du jour n'est peut-être pas encore jouée
        else:
            break
    return count


def leaderboard(game, limit=10):
    """Vainqueurs du jour : moins d'indices d'abord, puis les plus rapides."""
    return (MysteryAttempt.objects.filter(game=game, status=MysteryAttempt.STATUS_WON)
            .select_related('user')
            .order_by('clues_revealed', 'finished')[:limit])


def past_games():
    return MysteryGame.objects.filter(
        publish_date__lt=timezone.localdate(), status=MysteryGame.STATUS_APPROVED,
    ).select_related('author').order_by('-publish_date')


def week_ahead_missing():
    """Jours des 7 prochains jours sans jeu programmé (pour le panel)."""
    today = timezone.localdate()
    days = [today + timedelta(days=i) for i in range(7)]
    planned = set(MysteryGame.objects.filter(publish_date__in=days, status=MysteryGame.STATUS_APPROVED)
                  .values_list('publish_date', flat=True))
    return [day for day in days if day not in planned]


# --- Création et propositions ------------------------------------------------

CLUE_SLOTS = 6
MIN_CLUES = 3
MAX_PENDING_PROPOSALS = 5
XP_PROPOSAL_APPROVED = 25


def apply_form(game, data, files):
    """Remplit ``game`` et ses indices depuis un formulaire (membre ou équipe).

    Renvoie la liste des erreurs ; rien n'est enregistré s'il y en a.
    Le jeu doit être sauvegardé par l'appelant avant ``save_clues``.
    """
    errors = []
    title = data.get('title', '').strip()[:155]
    if not title:
        errors.append("Le nom du jeu (la réponse) est obligatoire.")
    clues = []
    for slot in range(1, CLUE_SLOTS + 1):
        text = data.get(f'clue_{slot}_text', '').strip()[:255]
        image = files.get(f'clue_{slot}_image')
        remove = bool(data.get(f'clue_{slot}_remove_image'))
        if text or image or _existing_clue(game, slot, keep_image=not remove):
            clues.append((slot, text, image, remove))
    if len(clues) < MIN_CLUES:
        errors.append(f"Il faut au moins {MIN_CLUES} indices, du plus vague au plus précis.")
    if errors:
        return errors, None
    game.title = title
    game.aliases = data.get('aliases', '').strip()
    game.anecdote = data.get('anecdote', '').strip()
    return [], clues


def _existing_clue(game, slot, keep_image=True):
    if not game.pk:
        return None
    clue = next((c for c in game.clues.all() if c.order == slot), None)
    if clue and keep_image and clue.image:
        return clue
    return None


def save_clues(game, clues):
    """Enregistre les indices, renumérotés de 1 à n dans l'ordre du formulaire."""
    existing = {clue.order: clue for clue in game.clues.all()}
    kept = []
    for order, (slot, text, image, remove) in enumerate(clues, start=1):
        clue = existing.get(slot) or MysteryClue(game=game)
        clue.text = text
        if image:
            clue.image = image
        elif remove:
            clue.image = None
        clue.order = order
        kept.append(clue)
    game.clues.exclude(pk__in=[c.pk for c in kept if c.pk]).delete()
    for clue in kept:
        clue.save()


def can_propose(user):
    pending = MysteryGame.objects.filter(author=user, status=MysteryGame.STATUS_PENDING).count()
    return pending < MAX_PENDING_PROPOSALS


def approve(game, moderator):
    """Valide une proposition : récompense l'auteur une seule fois et le prévient."""
    game.status = MysteryGame.STATUS_APPROVED
    game.rejection_reason = ''
    game.save(update_fields=['status', 'rejection_reason', 'updated'])
    rewarded = MysteryGame.objects.filter(pk=game.pk, reward_granted=False).update(reward_granted=True)
    if rewarded and game.author_id and game.author_id != moderator.pk:
        game.reward_granted = True
        grant_experience(game.author, XP_PROPOSAL_APPROVED, gold=GOLD_BIG_ACTION)
        _notify(moderator, game.author,
                f"Ton jeu mystère « {game.title} » est accepté",
                [f"Bonne nouvelle [b]{game.author.username}[/b] !",
                 "",
                 f"Ton jeu mystère [b]« {game.title} »[/b] a été validé par l'équipe. 🎉",
                 f"Tu gagnes [b]{XP_PROPOSAL_APPROVED} XP[/b] et [b]{GOLD_BIG_ACTION} pièces d'or[/b].",
                 "Il sera bientôt programmé comme jeu du jour. Ce jour-là, tu ne pourras pas y jouer "
                 "(tu connais la réponse 😉), mais ton nom sera affiché comme auteur.",
                 "",
                 "Merci pour ta contribution !"])


def reject(game, moderator, reason):
    game.status = MysteryGame.STATUS_REJECTED
    game.rejection_reason = reason
    game.publish_date = None
    game.save(update_fields=['status', 'rejection_reason', 'publish_date', 'updated'])
    if game.author_id and game.author_id != moderator.pk:
        lines = [f"Bonjour [b]{game.author.username}[/b],",
                 "",
                 f"Ton jeu mystère [b]« {game.title} »[/b] n'a pas pu être retenu en l'état."]
        if reason:
            lines += ["", f"[b]Raison :[/b] {reason}"]
        lines += ["", "Tu peux le modifier et le proposer à nouveau depuis la page « Mes propositions »."]
        _notify(moderator, game.author, f"Ton jeu mystère « {game.title} »", lines)


def _notify(moderator, receiver, subject, lines):
    try:
        from posts.notifications import _send
        _send(moderator, receiver, subject, "\n".join(lines))
    except Exception:
        # Un message de courtoisie ne doit jamais bloquer la modération.
        pass
