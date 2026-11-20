"""Déroulement du jeu : exploration, scènes, combats, économie, récompenses, vues."""
from django.test import override_settings
from django.urls import reverse

from shop.models import Item as ShopItem
from users.models import User, UserInventory

from ..engine import RpgError
from ..engine import character as hero
from ..engine import combat as fight
from ..engine import economy, rewards, scenes, world
from ..models import (
    Character, CharacterQuest, Choice, CoinExchange, Combat, InventoryItem, Item, Location, LocationExit, Monster,
    Scene, Wound,
)
from .helpers import FixedRng, IvakarTestCase


class WorldTests(IvakarTestCase):
    def test_locked_exit(self):
        exit = LocationExit.objects.get(from_location__slug='lisiere', to_location__slug='mine-abandonnee')
        self.character.location = exit.from_location
        self.character.save()
        with self.assertRaisesMessage(RpgError, "lanterne"):
            world.move(self.character, exit.pk)

    def test_move(self):
        exit = LocationExit.objects.get(from_location__slug='precalm', to_location__slug='lisiere')
        world.move(self.character, exit.pk)
        self.assertEqual(self.reload().location.slug, 'lisiere')

    def test_explore_can_start_a_combat(self):
        lisiere = Location.objects.get(slug='lisiere')
        lisiere.scenes.update(explore_weight=0)
        lisiere.calm_weight = 0
        lisiere.save()
        self.character.location = lisiere
        self.character.save()
        world.explore(self.character, FixedRng(1))
        self.assertTrue(Combat.objects.filter(character=self.character).exists())

    def test_busy_hero_cannot_move(self):
        self.character.scene = Scene.objects.get(slug='pot-casse')
        self.character.save()
        exit = LocationExit.objects.get(from_location__slug='precalm', to_location__slug='lisiere')
        with self.assertRaises(RpgError):
            world.move(self.character, exit.pk)


class SceneTests(IvakarTestCase):
    def enter(self, slug):
        self.character.scene = Scene.objects.get(slug=slug)
        self.character.save()

    def test_quest_start(self):
        self.enter('pot-casse')
        choice = Choice.objects.get(scene__slug='pot-casse', label__startswith="Demander")
        scenes.choose(self.character, choice.pk)
        c = self.reload()
        self.assertTrue(c.has_flag('quete_loups'))
        self.assertIsNone(c.scene)
        self.assertTrue(CharacterQuest.objects.filter(character=c, quest__slug='loups-lisiere').exists())

    def test_test_success_and_failure_use_2d6(self):
        self.enter('puits-ancien')
        choice = Choice.objects.get(scene__slug='puits-ancien', label__startswith="Scruter")
        self.set_stat('perception', 9)  # bonus 3
        scenes.choose(self.character, choice.pk, FixedRng(5, 5))  # 13 → réussite
        self.assertEqual(self.reload().coins, hero.STARTING_COINS + 12)

    def test_failed_test_can_wound_and_start_combat(self):
        self.character.flags = ['quete_loups']
        self.character.save()
        self.enter('taniere-loups')
        choice = Choice.objects.get(scene__slug='taniere-loups', label__startswith="Le contourner")
        self.set_stat('dexterite', 3)
        scenes.choose(self.character, choice.pk, FixedRng(1, 1))
        c = self.reload()
        self.assertEqual(Wound.objects.get(character=c).severity, Wound.SEVERITY_LIGHT)
        combat = Combat.objects.get(character=c)
        self.assertEqual((combat.monster.slug, combat.then_scene.slug), ('loup-alpha', 'taniere-apres'))

    def test_locked_choice(self):
        self.enter('colporteur-blesse')
        InventoryItem.objects.filter(inventory__character=self.character, item__slug='potion-soin').delete()
        choice = Choice.objects.get(scene__slug='colporteur-blesse', label__startswith="Lui donner")
        with self.assertRaises(RpgError):
            scenes.choose(self.character, choice.pk)

    def test_once_scene_is_not_drawn_again(self):
        scene = Scene.objects.get(slug='puits-ancien')
        world.enter_scene(self.character, scene)
        self.assertFalse(world.scene_is_eligible(self.character, scene))


class CombatTests(IvakarTestCase):
    def fight(self, slug='loup-gris', then_scene=None):
        fight.start_combat(self.character, Monster.objects.get(slug=slug), then_scene)
        return Combat.objects.get(character=self.character)

    def test_hit_and_damage(self):
        combat = self.fight()
        self.set_stat('dexterite', 9)
        # attaque 5+5+3 ≥ 10, dégâts 6 + ⌊15/3⌋ + 1 (bâton) = 12 → loup (12 PV) vaincu
        fight.act(self.character, 'attack', rng=FixedRng(5, 5, 6, 0))
        c = self.reload()
        self.assertFalse(Combat.objects.filter(pk=combat.pk).exists())
        self.assertEqual(c.victories, 1)
        self.assertEqual(c.xp, 12)

    def test_failed_dodge_hurts(self):
        self.fight()
        hp = self.reload().hp
        self.set_stat('dexterite', 3)
        # attaque ratée (1+1+1), esquive ratée (1+1+1), dégâts 4
        fight.act(self.character, 'attack', rng=FixedRng(1, 1, 1, 1, 4))
        self.assertEqual(self.reload().hp, hp - 4)

    def test_ko_in_combat(self):
        self.fight()
        c = self.reload()
        c.hp = 1
        c.save()
        self.set_stat('dexterite', 3)
        fight.act(c, 'attack', rng=FixedRng(1, 1, 1, 1, 4, 6, 6))
        c = self.reload()
        self.assertEqual(c.state, Character.STATE_KO)
        self.assertFalse(Combat.objects.filter(character=c).exists())
        self.assertEqual(Wound.objects.get(character=c).severity, Wound.SEVERITY_MODERATE)

    def test_cannot_flee_a_boss(self):
        self.fight('roi-brume')
        with self.assertRaises(RpgError):
            fight.act(self.character, 'flee')

    def test_victory_resumes_story(self):
        self.fight(then_scene=Scene.objects.get(slug='taniere-apres'))
        self.set_stat('dexterite', 9)
        fight.act(self.character, 'attack', rng=FixedRng(5, 5, 6, 0))
        self.assertEqual(self.reload().scene.slug, 'taniere-apres')


class EconomyTests(IvakarTestCase):
    def test_exchange_site_gold_for_coins(self):
        economy.exchange(self.user, 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.gold, 190)
        self.assertEqual(self.reload().coins, hero.STARTING_COINS + 100)
        self.assertEqual(CoinExchange.objects.count(), 1)

    def test_exchange_refused_without_enough_gold(self):
        User.objects.filter(pk=self.user.pk).update(gold=5)
        with self.assertRaises(RpgError):
            economy.exchange(self.user, 0)
        self.assertEqual(self.reload().coins, hero.STARTING_COINS)

    def test_no_reverse_exchange(self):
        self.assertFalse([name for name in dir(economy) if 'gold' in name.lower() and callable(getattr(economy, name))])

    def test_buy_and_sell(self):
        hero.change_coins(self.character, 100)
        self.character.save()
        sword = Item.objects.get(slug='epee-courte')
        economy.buy(self.character, sword.pk)
        self.assertEqual(self.reload().coins, hero.STARTING_COINS + 100 - 25)
        economy.sell(self.character, sword.pk)
        self.assertEqual(self.reload().coins, hero.STARTING_COINS + 100 - 25 + 12)


class SiteRewardTests(IvakarTestCase):
    def level_to(self, level):
        c = self.reload()
        hero.gain_xp(c, hero.xp_for_level(level) - c.xp)
        c.save()
        return self.reload()

    def test_title_at_level_5(self):
        c = self.level_to(5)
        self.assertEqual(rewards.current_title(c), "Aventurier d'Ivakar")

    def test_frame_at_level_10_and_granted_once(self):
        c = self.level_to(10)
        frame = ShopItem.objects.get(css_class='cadre-ivakar')
        self.assertTrue(UserInventory.objects.filter(user=self.user, item=frame).exists())
        self.assertFalse(frame.is_active)
        rewards.grant_level_rewards(c)
        self.assertEqual(UserInventory.objects.filter(user=self.user, item=frame).count(), 1)


class ViewTests(IvakarTestCase):
    def test_closed_to_members(self):
        User.objects.create_user(username='membre', password='pass')
        self.client.login(username='membre', password='pass')
        self.assertEqual(self.client.get(reverse('rpg_home')).status_code, 404)
        self.assertEqual(self.client.get(reverse('rpg_play')).status_code, 404)

    @override_settings(RPG_OPEN=True)
    def test_open_to_members(self):
        User.objects.create_user(username='membre', password='pass')
        self.client.login(username='membre', password='pass')
        self.assertEqual(self.client.get(reverse('rpg_home')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('rpg_play')), reverse('rpg_create'))

    def test_create_through_form(self):
        User.objects.create_user(username='chef', password='pass', is_staff=True)
        self.client.login(username='chef', password='pass')
        response = self.client.post(reverse('rpg_create'), {'name': 'Ysolde', 'origin': self.origin.pk})
        self.assertRedirects(response, reverse('rpg_play'))
        self.assertTrue(Character.objects.filter(name='Ysolde').exists())

    def test_pages_render(self):
        self.client.login(username='heros', password='pass')
        for name in ('rpg_home', 'rpg_play', 'rpg_sheet', 'rpg_inventory', 'rpg_quests', 'rpg_merchant',
                     'rpg_exchange', 'rpg_rewards'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_play_modes_render(self):
        self.client.login(username='heros', password='pass')
        self.character.scene = Scene.objects.get(slug='pot-casse')
        self.character.save()
        self.assertContains(self.client.get(reverse('rpg_play')), "Pot Cassé")
        self.character.scene = None
        self.character.save()
        fight.start_combat(self.character, Monster.objects.get(slug='loup-gris'))
        self.assertContains(self.client.get(reverse('rpg_play')), "Attaquer")
        Combat.objects.all().delete()
        Character.objects.filter(pk=self.character.pk).update(state=Character.STATE_KO)
        self.assertContains(self.client.get(reverse('rpg_play')), "Reprendre connaissance")

    def test_actions_require_post(self):
        self.client.login(username='heros', password='pass')
        self.assertEqual(self.client.get(reverse('rpg_explore')).status_code, 405)

    def test_portal_tile_for_staff_only_while_closed(self):
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('portal_games')), "Ivakar")
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('portal_games')), "Ivakar, le RPG")
