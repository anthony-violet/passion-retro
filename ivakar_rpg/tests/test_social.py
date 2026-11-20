"""Multijoueur : présence, taverne, échanges, duels, événements de serveur."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from users.models import User

from ..engine import RpgError
from ..engine import character as hero
from ..engine import duel as duel_engine
from ..engine import events, social, trade
from ..models import (
    Character, CharacterCharacteristic, Duel, EventParticipation, InventoryItem, Item, Location, LocationMessage, Trade, WorldEvent,
)
from .helpers import FixedRng, IvakarTestCase


class SocialTestCase(IvakarTestCase):
    def setUp(self):
        super().setUp()
        self.other_user = User.objects.create_user(username='compagnon', password='pass', is_staff=True)
        self.other = hero.create_character(self.other_user, "Brann", self.origin.pk)
        now = timezone.now()
        Character.objects.update(last_seen_at=now)
        self.reload()
        self.other.refresh_from_db()

    def qty(self, character, slug):
        entry = InventoryItem.objects.filter(inventory__character=character, item__slug=slug).first()
        return entry.quantity if entry else 0


class PresenceAndTavernTests(SocialTestCase):
    def test_present_heroes_same_location_and_recent(self):
        self.assertEqual(list(social.present_heroes(self.character)), [self.other])
        Character.objects.filter(pk=self.other.pk).update(last_seen_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(list(social.present_heroes(self.character)), [])
        Character.objects.filter(pk=self.other.pk).update(last_seen_at=timezone.now(),
                                                          location=Location.objects.get(slug='lisiere'))
        self.assertEqual(list(social.present_heroes(self.character)), [])

    def test_say_and_cooldown(self):
        social.say(self.character, "  Bonjour   la taverne ! ")
        self.assertEqual(LocationMessage.objects.get().text, "Bonjour la taverne !")
        with self.assertRaises(RpgError):
            social.say(self.character, "Encore moi")
        with self.assertRaises(RpgError):
            social.say(self.other, "x" * 301)

    def test_hidden_messages_are_not_shown(self):
        message = social.say(self.character, "Message déplacé")
        message.is_hidden = True
        message.save()
        self.assertEqual(social.tavern(self.character.location), [])

    def test_feed_is_escaped_json(self):
        social.say(self.other, "<script>alert(1)</script>")
        self.client.login(username='heros', password='pass')
        data = self.client.get(reverse('rpg_tavern_feed')).json()
        self.assertEqual(data['messages'][0]['text'], "<script>alert(1)</script>")  # le JS l'insère en texte
        self.assertEqual(data['present'][0]['name'], "Brann")
        page = self.client.get(reverse('rpg_play'))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;")

    def test_say_without_reload(self):
        self.client.login(username='heros', password='pass')
        url = reverse('rpg_tavern_say')
        response = self.client.post(url, {'text': 'Salut'}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.json(), {'ok': True})
        response = self.client.post(url, {'text': 'Encore'}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 400)
        self.assertIn('attends', response.json()['error'])
        self.assertRedirects(self.client.post(url, {'text': ''}), reverse('rpg_play'))

    def test_feed_after(self):
        first = social.say(self.other, "Un")
        self.client.login(username='heros', password='pass')
        data = self.client.get(reverse('rpg_tavern_feed'), {'after': first.pk}).json()
        self.assertEqual(data['messages'], [])


class TradeTests(SocialTestCase):
    def potion(self):
        return Item.objects.get(slug='potion-soin')

    def test_accept_transfers_items_and_coins(self):
        offer = trade.propose(self.character, self.other.pk, offer={self.potion().pk: 1}, request_coins=5)
        trade.accept(self.other, offer.pk)
        self.assertEqual(self.qty(self.character, 'potion-soin'), 1)
        self.assertEqual(self.qty(self.other, 'potion-soin'), 3)
        self.assertEqual(self.reload().coins, hero.STARTING_COINS + 5)
        self.other.refresh_from_db()
        self.assertEqual(self.other.coins, hero.STARTING_COINS - 5)
        self.assertEqual(Trade.objects.get().status, Trade.STATUS_ACCEPTED)

    def test_fails_cleanly_if_items_are_gone(self):
        offer = trade.propose(self.character, self.other.pk, offer={self.potion().pk: 2}, request_coins=3)
        InventoryItem.objects.filter(inventory__character=self.character, item__slug='potion-soin').delete()
        with self.assertRaises(RpgError):
            trade.accept(self.other, offer.pk)
        self.assertEqual(Trade.objects.get().status, Trade.STATUS_FAILED)
        self.other.refresh_from_db()
        self.assertEqual(self.other.coins, hero.STARTING_COINS)

    def test_quest_items_cannot_be_traded(self):
        croc = Item.objects.get(slug='croc-alpha')
        hero.add_item(self.character, croc)
        with self.assertRaises(RpgError):
            trade.propose(self.character, self.other.pk, offer={croc.pk: 1})

    def test_must_be_in_same_place(self):
        Character.objects.filter(pk=self.other.pk).update(location=Location.objects.get(slug='lisiere'))
        with self.assertRaises(RpgError):
            trade.propose(self.character, self.other.pk, offer_coins=1)

    def test_only_receiver_accepts_and_only_proposer_cancels(self):
        offer = trade.propose(self.character, self.other.pk, offer_coins=1)
        with self.assertRaises(RpgError):
            trade.accept(self.character, offer.pk)
        with self.assertRaises(RpgError):
            trade.cancel(self.other, offer.pk)
        trade.decline(self.other, offer.pk)
        self.assertEqual(Trade.objects.get().status, Trade.STATUS_DECLINED)

    def test_trade_pages(self):
        self.client.login(username='heros', password='pass')
        response = self.client.post(reverse('rpg_trade_new'), {
            'receiver': self.other.pk, f'offer_{self.potion().pk}': 1, 'offer_coins': 0, 'request_coins': 2})
        self.assertRedirects(response, reverse('rpg_trades'))
        self.client.login(username='compagnon', password='pass')
        self.assertContains(self.client.get(reverse('rpg_trades')), "te propose")
        self.client.post(reverse('rpg_trade_answer', args=[Trade.objects.get().pk]), {'action': 'accept'})
        self.assertEqual(Trade.objects.get().status, Trade.STATUS_ACCEPTED)


class DuelTests(SocialTestCase):
    def start(self):
        duel = duel_engine.challenge(self.character, self.other.pk)
        return duel_engine.accept(self.other, duel.pk)

    def test_challenge_accept_and_turns(self):
        duel = self.start()
        self.assertEqual(duel.status, Duel.STATUS_ACTIVE)
        self.assertEqual(duel.turn_id, self.other.pk)  # le défié commence
        with self.assertRaises(RpgError):
            duel_engine.act(self.character, duel.pk, 'attack')

    def test_attack_uses_2d6_and_guard(self):
        duel = self.start()
        self.set_stat('dexterite', 9)  # bonus +3
        duel_engine.act(self.other, duel.pk, 'defend')
        duel.refresh_from_db()
        self.assertEqual(duel.guarding_id, self.other.pk)
        # 5 + 5 + 3 = 13 < 16 (adversaire en garde) → raté
        duel_engine.act(self.character, duel.pk, 'attack', rng=FixedRng(5, 5))
        duel.refresh_from_db()
        self.assertEqual(duel.opponent_hp, duel.opponent_max_hp)

    def test_victory_without_real_damage(self):
        duel = self.start()
        hp_before = self.reload().hp
        Duel.objects.filter(pk=duel.pk).update(challenger_hp=1, turn=self.other)
        self.other.refresh_from_db()
        CharacterCharacteristic.objects.filter(character=self.other,
                                               characteristic__code='dexterite').update(value=30)
        duel_engine.act(self.other, duel.pk, 'attack', rng=FixedRng(6, 6, 6))
        duel.refresh_from_db()
        self.assertEqual((duel.status, duel.winner_id), (Duel.STATUS_FINISHED, self.other.pk))
        c = self.reload()
        self.assertEqual((c.hp, c.state, c.duel_losses), (hp_before, Character.STATE_OK, 1))

    def test_forfeit_and_claim(self):
        duel = self.start()
        with self.assertRaises(RpgError):
            duel_engine.claim_forfeit(self.character, duel.pk)
        Duel.objects.filter(pk=duel.pk).update(updated_at=timezone.now() - timedelta(hours=25))
        duel_engine.claim_forfeit(self.character, duel.pk)
        duel.refresh_from_db()
        self.assertEqual(duel.winner_id, self.character.pk)

    def test_one_active_duel_and_no_double_challenge(self):
        self.start()
        with self.assertRaises(RpgError):
            duel_engine.challenge(self.character, self.other.pk)

    def test_duel_pages(self):
        duel = self.start()
        self.client.login(username='compagnon', password='pass')
        self.assertContains(self.client.get(reverse('rpg_duel', args=[duel.pk])), "À toi de jouer")
        self.assertEqual(self.client.get(reverse('rpg_duel_state', args=[duel.pk])).json()['turn'], self.other.pk)
        intruder = User.objects.create_user(username='intrus', password='pass', is_staff=True)
        hero.create_character(intruder, "Intrus", self.origin.pk)
        self.client.login(username='intrus', password='pass')
        self.assertEqual(self.client.get(reverse('rpg_duel', args=[duel.pk])).status_code, 404)


class WorldEventTests(SocialTestCase):
    def make_event(self, **kwargs):
        now = timezone.now()
        values = dict(slug='ombre', name="L'Ombre d'Agasur", hp_total=20, starts_at=now - timedelta(hours=1),
                      ends_at=now + timedelta(days=1), reward_xp=30, reward_coins=10,
                      top_reward_item=Item.objects.get(slug='grande-potion'), cooldown_minutes=30)
        values.update(kwargs)
        return WorldEvent.objects.create(**values)

    def test_new_event_starts_full(self):
        event = self.make_event(hp_left=3)
        self.assertEqual(event.hp_left, 20)

    def test_attack_damage_and_cooldown(self):
        event = self.make_event()
        self.set_stat('dexterite', 9)
        # assaut 6+6+3 ≥ 13, dégâts 4 + 5 + 1 = 10 ; esquive 6+6+3 réussie
        events.attack(self.character, event.pk, rng=FixedRng(6, 6, 4, 6, 6))
        event.refresh_from_db()
        self.assertEqual(event.hp_left, 10)
        self.assertEqual(EventParticipation.objects.get().damage, 10)
        with self.assertRaises(RpgError):
            events.attack(self.character, event.pk)

    def test_victory_rewards_everyone_once(self):
        event = self.make_event()
        self.set_stat('dexterite', 9)
        events.attack(self.character, event.pk, rng=FixedRng(6, 6, 4, 6, 6))  # 10 dégâts
        events.attack(self.other, event.pk, rng=FixedRng(6, 6, 6))  # coup décisif
        event.refresh_from_db()
        self.assertTrue(event.is_defeated and event.rewards_given)
        c = self.reload()
        self.other.refresh_from_db()
        self.assertEqual(c.xp, 30)
        self.assertEqual(self.other.coins, hero.STARTING_COINS + 10)
        best = EventParticipation.objects.order_by('-damage').first().character
        self.assertEqual(self.qty(best, 'grande-potion'), 1)
        events.distribute_rewards(event)
        self.assertEqual(self.reload().xp, 30)

    def test_location_and_status(self):
        event = self.make_event(location=Location.objects.get(slug='lisiere'))
        with self.assertRaises(RpgError):
            events.attack(self.character, event.pk)
        late = self.make_event(slug='fini', ends_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(events.status(late), 'failed')
        with self.assertRaises(RpgError):
            events.attack(self.character, late.pk)

    def test_riposte_can_knock_out(self):
        event = self.make_event(damage_min=50, damage_max=50)
        self.set_stat('dexterite', 0)
        events.attack(self.character, event.pk, rng=FixedRng(1, 1, 1, 1, 50, 1, 1))
        self.assertEqual(self.reload().state, Character.STATE_KO)

    def test_event_page(self):
        event = self.make_event()
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('rpg_event')), "Lancer un assaut")
        self.client.post(reverse('rpg_event_attack', args=[event.pk]))
        self.assertEqual(EventParticipation.objects.count(), 1)
