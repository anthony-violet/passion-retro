"""Notifications des héros : popup (à fermer, pour ce qui demande une réponse ou marque un moment fort)
ou toast (éphémère, pour l'information).

Le style dépend du type de notification : voir ``KINDS``.
"""
from django.urls import reverse
from django.utils import timezone

from ..models import Notification

POPUP, TOAST = Notification.STYLE_POPUP, Notification.STYLE_TOAST

# type -> (style, icône)
KINDS = {
    'duel_challenge': (POPUP, "🤺"),
    'duel_accepted': (TOAST, "🤺"),
    'duel_declined': (TOAST, "🤺"),
    'duel_round': (TOAST, "⚔️"),
    'duel_your_move': (TOAST, "⏳"),
    'duel_finished': (POPUP, "🏆"),
    'trade_received': (POPUP, "🤝"),
    'trade_accepted': (TOAST, "🤝"),
    'trade_declined': (TOAST, "🤝"),
    'trade_failed': (TOAST, "🤝"),
    'level_up': (POPUP, "⭐"),
    'site_reward': (POPUP, "🏅"),
    'event_started': (POPUP, "🌍"),
    'event_won': (POPUP, "🌍"),
    'achievement': (POPUP, "🏆"),
    'daily_done': (TOAST, "✅"),
    'daily_all': (TOAST, "🎯"),
}
POLL_SECONDS = 10
MAX_DELIVERED = 10


def notify(character, kind, title, body='', url='', ref=''):
    """Crée une notification (une seule fois par ``ref`` si elle est donnée)."""
    if character is None:
        return None
    if ref and Notification.objects.filter(character=character, ref=ref).exists():
        return None
    style, _ = KINDS.get(kind, (TOAST, ''))
    return Notification.objects.create(character=character, kind=kind, style=style, title=title[:120],
                                       body=body[:300], url=url[:200], ref=ref[:60])


def deliver(character, now=None):
    """Notifications à afficher : les toasts sont considérés vus dès qu'ils partent, les popups restent
    jusqu'à ce que le joueur les ferme."""
    from .events import current_event

    now = now or timezone.now()
    event = current_event(now)
    if event is not None:
        notify(character, 'event_started', f"{event.name} menace le monde !",
               "Tous les héros sont appelés à combattre ensemble.", reverse('rpg_event_detail', args=[event.pk]),
               ref=f"event:{event.pk}")
    pending = list(Notification.objects.filter(character=character, seen_at=None)[:MAX_DELIVERED])
    toasts = [n.pk for n in pending if n.style == TOAST]
    if toasts:
        Notification.objects.filter(pk__in=toasts).update(seen_at=now)
    return [{
        'id': n.pk, 'kind': n.kind, 'style': n.style, 'icon': KINDS.get(n.kind, (TOAST, ''))[1], 'title': n.title,
        'body': n.body, 'url': n.url,
    } for n in pending]


def dismiss(character, notification_id, now=None):
    Notification.objects.filter(character=character, pk=notification_id, seen_at=None) \
        .update(seen_at=now or timezone.now())
