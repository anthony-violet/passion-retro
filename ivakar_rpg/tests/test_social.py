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
    """Les deux héros ont l'origine « Soldat » : Force 15, Dex 11 (+3), Perception 9 (+3), Intelligence 7 (+2),
    Mental 12 (+4), Charisme 8 (+2) ; bonus de dégâts = ⌊15 ÷ 3⌋ + 1 (bâton) = 6, armure 0."""

    def start(self):
        duel = duel_engine.challenge(self.character, self.other.pk)
        return duel_engine.accept(self.other, duel.pk)

    def play(self, duel, mine, theirs, rng):
        duel_engine.choose(self.character, duel.pk, mine)
        duel_engine.choose(self.other, duel.pk, theirs, rng=rng)
        duel.refresh_from_db()
        return duel

    def test_choices_stay_secret_until_both_have_chosen(self):
        duel = self.start()
        duel_engine.choose(self.character, duel.pk, 'strike')
        duel.refresh_from_db()
        state = duel_engine.view_state(duel, self.other)
        self.assertTrue(state['other_has_chosen'])
        self.assertEqual(state['revealed_action'], '')
        self.assertEqual(duel.round, 1)
        with self.assertRaises(RpgError):
            duel_engine.choose(self.character, duel.pk, 'guard')

    def test_strike_exchange_uses_opposition_and_degrees(self):
        duel = self.start()
        # Aldric : 6+6+3 = 15 contre 1+1+3 = 5 → écart 10, coup appuyé : 4 + 6 + 3 = 13.
        # Brann : 1+1+3 = 5 contre 6+6+3 = 15 → esquivé.
        duel = self.play(duel, 'strike', 'strike', FixedRng(6, 6, 1, 1, 4, 3, 1, 1, 6, 6))
        self.assertEqual(duel.opponent_hp, duel.opponent_max_hp - 13)
        self.assertEqual(duel.challenger_hp, duel.challenger_max_hp)
        self.assertEqual((duel.round, duel.challenger_action, duel.opponent_action), (2, '', ''))

    def test_tie_goes_to_defender(self):
        duel = self.start()
        duel = self.play(duel, 'strike', 'guard', FixedRng(3, 3, 3, 3))
        self.assertEqual(duel.opponent_hp, duel.opponent_max_hp)

    def test_guard_punishes_power(self):
        duel = self.start()
        # Riposte de Brann : 6+6+3 contre 1+1+3 → écart 10 : 2 + 6 + 2 = 10.
        duel = self.play(duel, 'power', 'guard', FixedRng(6, 6, 1, 1, 2, 2))
        self.assertEqual(duel.challenger_hp, duel.challenger_max_hp - 10)
        self.assertEqual(duel.opponent_hp, duel.opponent_max_hp)

    def test_feint_opens_guard(self):
        duel = self.start()
        # Intelligence 6+6+2 = 14 contre Perception 1+1+3 = 5 → écart 9 : 1 + 6 + 1 = 8.
        duel = self.play(duel, 'feint', 'guard', FixedRng(6, 6, 1, 1, 1, 1))
        self.assertEqual(duel.opponent_hp, duel.opponent_max_hp - 8)

    def test_feint_is_too_slow_against_an_attack(self):
        duel = self.start()
        duel = self.play(duel, 'feint', 'strike', FixedRng(1, 1, 1, 1))
        self.assertEqual(duel.opponent_hp, duel.opponent_max_hp)
        self.assertIn("trop lente", " ".join(e['text'] for e in duel.log))

    def test_log_is_split_into_readable_parts(self):
        duel = self.start()
        # Feinte 6+6 contre Perception 1+1 : touche ; la garde ne fait rien.
        duel = self.play(duel, 'feint', 'guard', FixedRng(6, 6, 1, 1, 1, 1))
        lines = [e for e in duel.log if e['round'] == 1]
        kinds = [e['kind'] for e in lines]
        self.assertEqual(kinds[:3], ['story', 'cast', 'cast'])
        self.assertIn('roll', kinds)
        self.assertEqual(kinds[-1], 'summary')
        hit = next(e for e in lines if e['kind'] == 'hit')
        self.assertEqual(hit['parts'][0], ['o', self.other.name])
        self.assertIn(['dmg', '8'], hit['parts'])
        roll = next(e for e in lines if e['kind'] == 'roll')
        self.assertIn("2D6 (6+6)", roll['detail'])
        self.client.login(username='heros', password='pass')
        page = self.client.get(reverse('rpg_duel', args=[duel.pk]))
        self.assertContains(page, '<span class="ivk-l-dmg">8</span>', html=True)
        self.assertContains(page, 'data-duel-dice')

    def test_intimidation_limits_next_round(self):
        duel = self.start()
        duel = self.play(duel, 'intimidate', 'guard', FixedRng(6, 6, 1, 1))
        self.assertTrue(duel.opponent_shaken)
        self.assertEqual(duel_engine.allowed_actions(duel, self.other), ('strike', 'guard'))
        with self.assertRaises(RpgError):
            duel_engine.choose(self.other, duel.pk, 'power')
        duel = self.play(duel, 'guard', 'strike', FixedRng(1, 1, 6, 6))
        self.assertFalse(duel.opponent_shaken)

    def test_observe_reveals_next_choice(self):
        duel = self.start()
        duel = self.play(duel, 'observe', 'guard', FixedRng(6, 6, 1, 1))
        self.assertTrue(duel.challenger_insight)
        duel_engine.choose(self.other, duel.pk, 'power')
        duel.refresh_from_db()
        self.assertEqual(duel_engine.view_state(duel, self.character)['revealed_action'], 'power')
        duel_engine.choose(self.character, duel.pk, 'guard', rng=FixedRng(6, 6, 1, 1, 1, 1))
        duel.refresh_from_db()
        self.assertFalse(duel.challenger_insight)

    def test_victory_without_real_damage(self):
        duel = self.start()
        hp_before = self.reload().hp
        Duel.objects.filter(pk=duel.pk).update(challenger_hp=1)
        duel = self.play(duel, 'guard', 'strike', FixedRng(6, 6, 1, 1, 1, 1))
        self.assertEqual((duel.status, duel.winner_id), (Duel.STATUS_FINISHED, self.other.pk))
        c = self.reload()
        self.assertEqual((c.hp, c.state, c.duel_losses), (hp_before, Character.STATE_OK, 1))

    def test_double_knockdown_is_a_draw(self):
        duel = self.start()
        Duel.objects.filter(pk=duel.pk).update(challenger_hp=1, opponent_hp=1)
        duel = self.play(duel, 'strike', 'strike', FixedRng(6, 6, 1, 1, 1, 1, 6, 6, 1, 1, 1, 1))
        self.assertEqual((duel.status, duel.winner_id), (Duel.STATUS_FINISHED, None))
        self.assertEqual((self.reload().duel_wins, self.reload().duel_losses), (0, 0))

    def test_forfeit_and_claim(self):
        duel = self.start()
        with self.assertRaises(RpgError):
            duel_engine.claim_forfeit(self.character, duel.pk)
        duel_engine.choose(self.character, duel.pk, 'guard')
        Duel.objects.filter(pk=duel.pk).update(updated_at=timezone.now() - timedelta(hours=25))
        duel_engine.claim_forfeit(self.character, duel.pk)
        duel.refresh_from_db()
        self.assertEqual(duel.winner_id, self.character.pk)
        other_duel = duel_engine.accept(self.other, duel_engine.challenge(self.character, self.other.pk).pk)
        duel_engine.forfeit(self.other, other_duel.pk)
        other_duel.refresh_from_db()
        self.assertEqual(other_duel.winner_id, self.character.pk)

    def test_one_active_duel_and_no_double_challenge(self):
        self.start()
        with self.assertRaises(RpgError):
            duel_engine.challenge(self.character, self.other.pk)

    def test_waiting_counter(self):
        duel = self.start()
        self.assertEqual(duel_engine.waiting_for(self.character).count(), 1)
        duel_engine.choose(self.character, duel.pk, 'guard')
        self.assertEqual(duel_engine.waiting_for(self.character).count(), 0)
        self.assertEqual(duel_engine.waiting_for(self.other).count(), 1)

    def test_challenger_waits_on_a_refreshing_page(self):
        self.client.login(username='heros', password='pass')
        response = self.client.post(reverse('rpg_duel_challenge', args=[self.other.pk]))
        duel = Duel.objects.get()
        self.assertRedirects(response, reverse('rpg_duel', args=[duel.pk]))
        page = self.client.get(reverse('rpg_duel', args=[duel.pk]))
        self.assertContains(page, "En attente de la réponse")
        self.assertContains(page, 'data-state=')  # le script de rafraîchissement est présent
        state_url = reverse('rpg_duel_state', args=[duel.pk])
        self.assertEqual(self.client.get(state_url).json()['status'], Duel.STATUS_PENDING)
        duel_engine.accept(self.other, duel.pk)
        self.assertEqual(self.client.get(state_url).json()['status'], Duel.STATUS_ACTIVE)

    def test_challenged_can_answer_from_the_duel_page(self):
        duel = duel_engine.challenge(self.character, self.other.pk)
        self.client.login(username='compagnon', password='pass')
        self.assertContains(self.client.get(reverse('rpg_duel', args=[duel.pk])), "Accepter")
        self.client.post(reverse('rpg_duel_answer', args=[duel.pk]), {'action': 'accept'})
        duel.refresh_from_db()
        self.assertEqual(duel.status, Duel.STATUS_ACTIVE)

    def test_duel_list_reacts_to_notifications(self):
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('rpg_duels')), "ivakar:notification")

    def test_duel_pages(self):
        duel = self.start()
        self.client.login(username='compagnon', password='pass')
        page = self.client.get(reverse('rpg_duel', args=[duel.pk]))
        for label in ("Frappe", "Coup puissant", "Garde", "Feinte", "Intimidation", "Observer"):
            self.assertContains(page, label)
        self.client.post(reverse('rpg_duel_action', args=[duel.pk]), {'action': 'guard'})
        self.assertContains(self.client.get(reverse('rpg_duel', args=[duel.pk])), "En attente du choix")
        self.client.login(username='heros', password='pass')
        state = self.client.get(reverse('rpg_duel_state', args=[duel.pk])).json()
        self.assertEqual((state['other_has_chosen'], state['revealed']), (True, ''))
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
