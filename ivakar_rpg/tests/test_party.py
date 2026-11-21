"""Groupes : invitations, discussion de groupe, combats à plusieurs."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from users.models import User

from ..engine import RpgError
from ..engine import character as hero
from ..engine import combat as fight
from ..engine import party, world
from ..models import (
    Character, CharacterCharacteristic, Combat, CombatReport, CombatSeat, Location, Monster, Notification, Party, PartyInvite,
    PartyMember, PartyMessage,
)
from .helpers import IvakarTestCase


class MaxRng:
    """Faux hasard : toujours la valeur maximale (2D6 = 12 des deux côtés : la caractéristique tranche)."""

    def randint(self, a, b):
        return b


class PartyTestCase(IvakarTestCase):
    def setUp(self):
        super().setUp()
        self.brann = self.make_hero('compagnon', "Brann")
        self.cyra = self.make_hero('troisieme', "Cyra")
        self.reload()

    def make_hero(self, username, name):
        user = User.objects.create_user(username=username, password='pass', is_staff=True)
        character = hero.create_character(user, name, self.origin.pk)
        Character.objects.filter(pk=character.pk).update(last_seen_at=timezone.now())
        character.refresh_from_db()
        return character

    def group(self, *others):
        """Aldric chef, les autres membres."""
        for other in others:
            party.invite(self.character, other.pk)
            party.accept(other, PartyInvite.objects.get(character=other).pk)
        return party.party_of(self.character)

    def stat(self, character, code, value):
        CharacterCharacteristic.objects.filter(character=character, characteristic__code=code).update(value=value)


class InviteTests(PartyTestCase):
    def test_invite_founds_party_and_accept_joins(self):
        party.invite(self.character, self.brann.pk)
        group = Party.objects.get()
        self.assertEqual(group.leader, self.character)
        self.assertTrue(Notification.objects.filter(character=self.brann, kind='party_invite').exists())
        party.accept(self.brann, PartyInvite.objects.get().pk)
        self.assertEqual(party.members(group), [self.character, self.brann])
        self.assertFalse(PartyInvite.objects.exists())
        self.assertTrue(Notification.objects.filter(character=self.character, kind='party_joined').exists())

    def test_invite_requires_same_location(self):
        Character.objects.filter(pk=self.brann.pk).update(location=Location.objects.get(slug='lisiere'))
        with self.assertRaises(RpgError):
            party.invite(self.character, self.brann.pk)
        self.assertFalse(Party.objects.exists())  # le groupe fondé pour l'occasion est annulé

    def test_only_leader_invites_and_members_cannot_be_invited(self):
        self.group(self.brann)
        with self.assertRaises(RpgError):
            party.invite(self.brann, self.cyra.pk)
        with self.assertRaises(RpgError):
            party.invite(self.cyra, self.brann.pk)

    def test_party_size_counts_invites(self):
        self.group(self.brann, self.cyra)
        d = self.make_hero('quatre', "Dorn")
        party.invite(self.character, d.pk)
        e = self.make_hero('cinq', "Elna")
        with self.assertRaises(RpgError):
            party.invite(self.character, e.pk)

    def test_decline_dissolves_lonely_party(self):
        party.invite(self.character, self.brann.pk)
        party.decline(self.brann, PartyInvite.objects.get().pk)
        self.assertFalse(Party.objects.exists())


class DepartureTests(PartyTestCase):
    def test_leader_leaving_promotes_oldest_member(self):
        group = self.group(self.brann, self.cyra)
        party.leave(self.character)
        group.refresh_from_db()
        self.assertEqual(group.leader, self.brann)
        self.assertEqual(party.members(group), [self.brann, self.cyra])

    def test_party_of_one_is_dissolved(self):
        self.group(self.brann)
        party.leave(self.brann)
        self.assertFalse(Party.objects.exists())
        self.assertFalse(PartyMember.objects.exists())

    def test_kick_and_promote(self):
        group = self.group(self.brann, self.cyra)
        with self.assertRaises(RpgError):
            party.kick(self.brann, self.cyra.pk)
        party.kick(self.character, self.cyra.pk)
        self.assertEqual(party.members(group), [self.character, self.brann])
        self.assertTrue(Notification.objects.filter(character=self.cyra, kind='party_kicked').exists())
        party.promote(self.character, self.brann.pk)
        group.refresh_from_db()
        self.assertEqual(group.leader, self.brann)


class ChatTests(PartyTestCase):
    def test_say_reaches_members_wherever_they_are(self):
        self.group(self.brann)
        Character.objects.filter(pk=self.brann.pk).update(location=Location.objects.get(slug='lisiere'))
        party.say(self.character, "  On se retrouve à   l'auberge ? ")
        self.assertEqual(PartyMessage.objects.get().text, "On se retrouve à l'auberge ?")
        with self.assertRaises(RpgError):
            party.say(self.character, "Encore")
        self.client.login(username='compagnon', password='pass')
        data = self.client.get(reverse('rpg_party_feed')).json()
        self.assertEqual([m['text'] for m in data['messages']], ["On se retrouve à l'auberge ?"])
        self.assertEqual(len(data['members']), 2)

    def test_outsiders_see_nothing(self):
        self.group(self.brann)
        party.say(self.character, "Secret de groupe")
        with self.assertRaises(RpgError):
            party.say(self.cyra, "Je m'incruste")
        self.client.login(username='troisieme', password='pass')
        self.assertEqual(self.client.get(reverse('rpg_party_feed')).json(),
                         {'party': False, 'messages': [], 'members': []})

    def test_party_page_renders(self):
        self.group(self.brann)
        self.client.login(username='heros', password='pass')
        response = self.client.get(reverse('rpg_party'))
        self.assertContains(response, "Brann")
        self.assertContains(response, "Quitter le groupe")


class GroupCombatTests(PartyTestCase):
    """Loup gris : 12 PV, Dextérité 9 (bonus 3), Intelligence 3."""

    def setUp(self):
        super().setUp()
        self.wolf = Monster.objects.get(slug='loup-gris')

    def engage(self, *allies):
        fight.start_combat(self.character, self.wolf, rng=MaxRng())
        combat = Combat.objects.get(character=self.character)
        for ally in allies:
            fight.join(ally, combat.pk)
        combat.refresh_from_db()
        return combat

    def test_help_call_reaches_mates_here_only(self):
        self.group(self.brann, self.cyra)
        Character.objects.filter(pk=self.cyra.pk).update(location=Location.objects.get(slug='lisiere'))
        self.engage()
        self.assertTrue(Notification.objects.filter(character=self.brann, kind='party_help').exists())
        self.assertFalse(Notification.objects.filter(character=self.cyra, kind='party_help').exists())
        self.reload()
        self.brann.refresh_from_db()
        self.assertEqual([c.character for c in fight.joinable(self.brann)], [self.character])

    def test_join_requires_party_and_same_location(self):
        combat = self.engage()
        with self.assertRaises(RpgError):
            fight.join(self.brann, combat.pk)  # pas du même groupe
        self.group(self.brann)
        Character.objects.filter(pk=self.brann.pk).update(location=Location.objects.get(slug='lisiere'))
        with self.assertRaises(RpgError):
            fight.join(self.brann, combat.pk)

    def test_join_makes_a_group_combat_and_strengthens_the_monster(self):
        self.group(self.brann)
        combat = self.engage(self.brann)
        self.assertEqual(CombatSeat.objects.filter(combat=combat).count(), 2)
        self.assertEqual(combat.monster_max_hp, 18)
        self.assertEqual(combat.monster_hp, 18)
        self.assertEqual(combat.monster_target, self.character)
        self.assertEqual(fight.current_combat(self.brann), combat)
        with self.assertRaises(RpgError):
            world.explore(self.brann)  # en plein combat

    def test_round_waits_for_everyone_then_rewards_each_in_full(self):
        self.group(self.brann)
        for h in (self.character, self.brann):
            self.stat(h, 'dexterite', 30)
        combat = self.engage(self.brann)
        fight.act(self.character, 'strike', rng=MaxRng())
        combat.refresh_from_db()
        self.assertEqual(combat.turn, 1)  # Brann n'a pas encore choisi
        self.assertTrue(Notification.objects.filter(character=self.brann, kind='party_combat',
                                                    title__contains="a choisi").exists())
        with self.assertRaises(RpgError):
            fight.act(self.character, 'guard', rng=MaxRng())  # déjà choisi
        fight.act(self.brann, 'strike', rng=MaxRng())
        self.assertFalse(Combat.objects.exists())
        for h in (self.reload(), Character.objects.get(pk=self.brann.pk)):
            self.assertEqual(h.victories, 1)
            self.assertEqual(h.xp, self.wolf.xp)

    def test_force_round_after_timeout(self):
        self.group(self.brann)
        combat = self.engage(self.brann)
        fight.act(self.character, 'observe', rng=MaxRng())
        with self.assertRaises(RpgError):
            fight.force_round(self.character, rng=MaxRng())
        Combat.objects.filter(pk=combat.pk).update(round_started_at=timezone.now() - timedelta(minutes=5))
        fight.force_round(self.character, rng=MaxRng())
        combat.refresh_from_db()
        self.assertEqual(combat.turn, 2)
        self.assertFalse(CombatSeat.objects.filter(combat=combat).exclude(action='').exists())

    def test_fallen_owner_hands_the_fight_to_the_survivor(self):
        self.group(self.brann)
        combat = self.engage(self.brann)
        self.stat(self.character, 'dexterite', 1)
        Character.objects.filter(pk=self.character.pk).update(hp=1)
        Combat.objects.filter(pk=combat.pk).update(monster_action='strike', monster_target=self.character)
        fight.act(self.character, 'observe', rng=MaxRng())
        fight.act(self.brann, 'observe', rng=MaxRng())
        me = self.reload()
        self.assertTrue(me.is_ko)
        combat = Combat.objects.get(pk=combat.pk)
        self.assertEqual(combat.character, self.brann)
        self.assertFalse(CombatSeat.objects.exists())  # seul survivant : retour au combat solo
        self.assertIsNone(fight.current_combat(me))

    def test_feint_catches_a_monster_busy_with_someone_else(self):
        self.group(self.brann)
        combat = self.engage(self.brann)
        self.stat(self.brann, 'intelligence', 30)
        Combat.objects.filter(pk=combat.pk).update(monster_action='strike', monster_target=self.character,
                                                   monster_hp=100, monster_max_hp=100)
        fight.act(self.character, 'guard', rng=MaxRng())
        fight.act(self.brann, 'feint', rng=MaxRng())
        combat.refresh_from_db()
        self.assertLess(combat.monster_hp, 100)
        self.assertIn("pris au dépourvu", ' '.join(e['text'] for e in combat.log))

    def test_successful_flight_leaves_the_others_fighting(self):
        self.group(self.brann)
        combat = self.engage(self.brann)
        self.stat(self.brann, 'dexterite', 30)
        fight.act(self.character, 'guard', rng=MaxRng())
        fight.act(self.brann, 'flee', rng=MaxRng())
        combat.refresh_from_db()
        self.assertEqual(combat.character, self.character)
        self.assertFalse(CombatSeat.objects.exists())
        self.assertIsNone(fight.current_combat(Character.objects.get(pk=self.brann.pk)))

    def test_play_page_shows_group_and_join_button(self):
        self.group(self.brann)
        self.engage()
        self.client.login(username='compagnon', password='pass')
        self.assertContains(self.client.get(reverse('rpg_play')), "Rejoindre le combat")
        combat = Combat.objects.get()
        self.client.post(reverse('rpg_combat_join', args=[combat.pk]))
        response = self.client.get(reverse('rpg_play'))
        self.assertContains(response, "rpg-party-fighters")
        self.assertEqual(self.client.get(reverse('rpg_combat_state')).json()['fighters'], 2)


class CombatReportTests(PartyTestCase):
    """Rapport remis à chaque héros quand le combat se termine pour lui."""

    def setUp(self):
        super().setUp()
        self.wolf = Monster.objects.get(slug='loup-gris')

    def test_solo_victory_report_and_play_page(self):
        self.stat(self.character, 'dexterite', 30)
        fight.start_combat(self.character, self.wolf, rng=MaxRng())
        Combat.objects.filter(character=self.character).update(monster_action='strike')
        fight.act(self.character, 'strike', rng=MaxRng())
        report = CombatReport.objects.get(character=self.character)
        self.assertEqual(report.outcome, CombatReport.OUTCOME_VICTORY)
        self.assertEqual(report.rewards['xp'], self.wolf.xp)
        self.assertEqual(report.stats[0]['name'], "Aldric")
        self.assertGreaterEqual(report.stats[0]['dealt'], self.wolf.hp)
        self.assertTrue(any(e['kind'] == 'end' for e in report.log))
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('rpg_play')), "Victoire contre Loup gris")
        self.client.post(reverse('rpg_report_close'))
        self.assertNotContains(self.client.get(reverse('rpg_play')), "Rapport de combat")
        self.assertContains(self.client.get(reverse('rpg_reports')), "Loup gris")
        self.assertContains(self.client.get(reverse('rpg_report', args=[report.pk])), "Revoir le déroulé")

    def test_solo_knockout_report_mentions_the_wound(self):
        self.stat(self.character, 'dexterite', 1)
        Character.objects.filter(pk=self.character.pk).update(hp=1)
        fight.start_combat(self.reload(), self.wolf, rng=MaxRng())
        Combat.objects.filter(character=self.character).update(monster_action='strike')
        fight.act(self.character, 'observe', rng=MaxRng())
        report = CombatReport.objects.get(character=self.character)
        self.assertEqual(report.outcome, CombatReport.OUTCOME_KO)
        self.assertTrue(report.rewards['wound'])

    def test_solo_flight_report(self):
        self.stat(self.character, 'dexterite', 30)
        fight.start_combat(self.character, self.wolf, rng=MaxRng())
        fight.act(self.character, 'flee', rng=MaxRng())
        self.assertEqual(CombatReport.objects.get(character=self.character).outcome, CombatReport.OUTCOME_FLED)

    def test_group_reports_list_every_fighter(self):
        self.group(self.brann)
        for h in (self.character, self.brann):
            self.stat(h, 'dexterite', 30)
        fight.start_combat(self.character, self.wolf, rng=MaxRng())
        fight.join(self.brann, Combat.objects.get().pk)
        fight.act(self.character, 'strike', rng=MaxRng())
        fight.act(self.brann, 'strike', rng=MaxRng())
        for h in (self.character, self.brann):
            report = CombatReport.objects.get(character=h)
            self.assertEqual(report.outcome, CombatReport.OUTCOME_VICTORY)
            self.assertEqual({row['name'] for row in report.stats}, {"Aldric", "Brann"})
            self.assertEqual(report.stats[0]['id'], h.pk)  # le héros du rapport en premier
            self.assertGreaterEqual(sum(row['dealt'] for row in report.stats), 18)

    def test_fallen_group_member_gets_a_report_while_the_fight_goes_on(self):
        self.group(self.brann)
        fight.start_combat(self.character, self.wolf, rng=MaxRng())
        combat = Combat.objects.get()
        fight.join(self.brann, combat.pk)
        self.stat(self.character, 'dexterite', 1)
        Character.objects.filter(pk=self.character.pk).update(hp=1)
        Combat.objects.filter(pk=combat.pk).update(monster_action='strike', monster_target=self.character)
        fight.act(self.character, 'observe', rng=MaxRng())
        fight.act(self.brann, 'observe', rng=MaxRng())
        report = CombatReport.objects.get(character=self.character)
        self.assertEqual((report.outcome, report.rounds), (CombatReport.OUTCOME_KO, 1))
        self.assertFalse(CombatReport.objects.filter(character=self.brann).exists())
        self.assertTrue(Combat.objects.filter(pk=combat.pk).exists())
