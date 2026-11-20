"""Notifications : popup ou toast selon le type, déclenchées par le jeu, livrées par le point d'accès."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from ..engine import character as hero
from ..engine import duel as duel_engine
from ..engine import notifications, trade
from ..models import Item, Notification, WorldEvent
from .test_social import SocialTestCase


def kinds(character):
    return list(Notification.objects.filter(character=character).values_list('kind', 'style'))


class NotificationTests(SocialTestCase):
    def test_duel_flow(self):
        duel = duel_engine.challenge(self.character, self.other.pk)
        self.assertEqual(kinds(self.other), [('duel_challenge', 'popup')])
        duel_engine.accept(self.other, duel.pk)
        self.assertEqual(kinds(self.character), [('duel_accepted', 'toast')])
        duel_engine.choose(self.character, duel.pk, 'guard')
        self.assertIn(('duel_your_move', 'toast'), kinds(self.other))
        duel_engine.forfeit(self.character, duel.pk)
        self.assertIn(('duel_finished', 'popup'), kinds(self.other))

    def test_round_resolution_notifies_the_first_to_choose(self):
        from .helpers import FixedRng
        duel = duel_engine.accept(self.other, duel_engine.challenge(self.character, self.other.pk).pk)
        duel_engine.choose(self.character, duel.pk, 'guard')
        duel_engine.choose(self.other, duel.pk, 'guard', rng=FixedRng())
        self.assertIn(('duel_round', 'toast'), kinds(self.character))

    def test_trade_flow(self):
        potion = Item.objects.get(slug='potion-soin')
        offer = trade.propose(self.character, self.other.pk, offer={potion.pk: 1})
        self.assertEqual(kinds(self.other), [('trade_received', 'popup')])
        trade.accept(self.other, offer.pk)
        self.assertIn(('trade_accepted', 'toast'), kinds(self.character))
        refused = trade.propose(self.character, self.other.pk, offer_coins=1)
        trade.decline(self.other, refused.pk)
        self.assertIn(('trade_declined', 'toast'), kinds(self.character))

    def test_level_up_and_site_reward_are_popups(self):
        c = self.reload()
        hero.gain_xp(c, hero.xp_for_level(5))
        c.save()
        found = kinds(c)
        self.assertIn(('level_up', 'popup'), found)
        self.assertIn(('site_reward', 'popup'), found)

    def test_event_started_once_per_hero(self):
        now = timezone.now()
        WorldEvent.objects.create(slug='ombre', name="L'Ombre", hp_total=10, starts_at=now - timedelta(minutes=1),
                                  ends_at=now + timedelta(hours=1))
        notifications.deliver(self.character)
        notifications.deliver(self.character)
        self.assertEqual(kinds(self.character), [('event_started', 'popup')])

    def test_toasts_are_seen_on_delivery_popups_on_dismiss(self):
        toast = notifications.notify(self.character, 'trade_declined', "Refusé")
        popup = notifications.notify(self.character, 'trade_received', "Proposition")
        first = notifications.deliver(self.character)
        self.assertEqual({n['style'] for n in first}, {'toast', 'popup'})
        second = notifications.deliver(self.character)
        self.assertEqual([n['id'] for n in second], [popup.pk])
        notifications.dismiss(self.character, popup.pk)
        self.assertEqual(notifications.deliver(self.character), [])
        self.assertIsNotNone(Notification.objects.get(pk=toast.pk).seen_at)

    def test_cannot_dismiss_someone_else(self):
        popup = notifications.notify(self.other, 'trade_received', "Proposition")
        notifications.dismiss(self.character, popup.pk)
        self.assertIsNone(Notification.objects.get(pk=popup.pk).seen_at)

    def test_endpoints(self):
        notifications.notify(self.character, 'duel_challenge', "Défi", url=reverse('rpg_duels'))
        self.client.login(username='heros', password='pass')
        data = self.client.get(reverse('rpg_notifications')).json()
        self.assertEqual(data['notifications'][0]['style'], 'popup')
        self.assertEqual(data['notifications'][0]['icon'], "🤺")
        notification_id = data['notifications'][0]['id']
        self.assertEqual(self.client.get(reverse('rpg_notification_dismiss', args=[notification_id])).status_code,
                         405)
        self.client.post(reverse('rpg_notification_dismiss', args=[notification_id]))
        self.assertEqual(self.client.get(reverse('rpg_notifications')).json()['notifications'], [])

    def test_pages_include_notification_ui(self):
        self.client.login(username='heros', password='pass')
        page = self.client.get(reverse('rpg_play'))
        self.assertContains(page, 'data-ivk-notifications')
        self.assertContains(page, 'ivakar_notifications.js')
