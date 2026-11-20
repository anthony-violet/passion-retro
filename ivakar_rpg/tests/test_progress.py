"""Objectifs : tâches quotidiennes et succès."""
from datetime import timedelta

from django.urls import reverse

from ..engine import character as hero
from ..engine import progress
from ..models import Achievement, CharacterAchievement, CharacterDailyTask, DailyTask, Notification
from .helpers import FixedRng, IvakarTestCase


class DailyTaskTests(IvakarTestCase):
    def test_three_tasks_drawn_once_a_day(self):
        first = progress.ensure_today(self.character)
        self.assertEqual(len(first), progress.DAILY_COUNT)
        self.assertEqual(len({e.task_id for e in first}), progress.DAILY_COUNT)
        self.assertEqual([e.pk for e in progress.ensure_today(self.character)], [e.pk for e in first])
        tomorrow = progress.today() + timedelta(days=1)
        self.assertEqual(len(progress.ensure_today(self.character, day=tomorrow)), progress.DAILY_COUNT)

    def test_level_limits_the_draw(self):
        DailyTask.objects.exclude(slug='grande-chasse').update(is_active=False)
        self.assertEqual(progress.ensure_today(self.character), [])

    def test_progress_counts_from_the_draw(self):
        DailyTask.objects.exclude(slug='ronde-du-jour').update(is_active=False)
        self.character.explorations = 7
        self.character.save()
        entry = progress.ensure_today(self.character, rng=FixedRng(1))[0]
        self.assertEqual(entry.baseline, 7)
        self.character.explorations = 10
        self.character.save()
        self.assertEqual(progress.daily_view(self.character)[0]['progress'], 3)
        self.assertFalse(progress.update(self.character))

    def test_completion_rewards_and_full_day_bonus(self):
        DailyTask.objects.exclude(slug='ronde-du-jour').update(is_active=False)
        task = DailyTask.objects.get(slug='ronde-du-jour')
        progress.ensure_today(self.character, rng=FixedRng(1))
        coins = self.character.coins
        self.character.explorations = task.goal
        self.character.save()
        self.assertTrue(progress.update(self.character))
        c = self.reload()
        self.assertIsNotNone(CharacterDailyTask.objects.get(character=c).completed_at)
        self.assertEqual(c.daily_tasks_done, 1)
        self.assertEqual(c.coins, coins + task.reward_coins + progress.DAILY_BONUS_COINS)
        self.assertEqual(c.daily_bonus_day, progress.today())
        kinds = set(Notification.objects.filter(character=c).values_list('kind', flat=True))
        self.assertTrue({'daily_done', 'daily_all'} <= kinds)
        # Rien n'est versé deux fois.
        self.assertFalse(progress.update(c))
        self.assertEqual(self.reload().coins, coins + task.reward_coins + progress.DAILY_BONUS_COINS)

    def test_exploring_counts(self):
        from ..engine import world
        self.character.save()
        world.explore(self.character, FixedRng(1))
        self.assertEqual(self.reload().explorations, 1)


class AchievementTests(IvakarTestCase):
    def setUp(self):
        super().setUp()
        DailyTask.objects.update(is_active=False)  # isoler les succès

    def test_first_victory_unlocks_with_reward_and_popup(self):
        achievement = Achievement.objects.get(slug='premier-sang')
        self.character.victories = 1
        self.character.save()
        xp = self.character.xp
        progress.update(self.character)
        c = self.reload()
        self.assertTrue(CharacterAchievement.objects.filter(character=c, achievement=achievement).exists())
        self.assertEqual(c.xp, xp + achievement.reward_xp)
        self.assertEqual(Notification.objects.get(character=c, kind='achievement').style, 'popup')
        progress.update(c)
        self.assertEqual(CharacterAchievement.objects.filter(character=c, achievement=achievement).count(), 1)

    def test_flag_achievement(self):
        achievement = Achievement.objects.get(slug='tombeur-du-roi')
        self.character.flags = ['roi_vaincu']
        self.character.save()
        progress.update(self.character)
        self.assertTrue(CharacterAchievement.objects.filter(character=self.character, achievement=achievement)
                        .exists())

    def test_reward_xp_can_chain_into_a_level_achievement(self):
        Achievement.objects.create(slug='palier', name="Palier", metric='victories', goal=1,
                                   reward_xp=hero.xp_for_level(5))
        self.character.victories = 1
        self.character.save()
        progress.update(self.character)
        unlocked = set(CharacterAchievement.objects.filter(character=self.character)
                       .values_list('achievement__slug', flat=True))
        self.assertIn('heros-confirme', unlocked)

    def test_secret_stays_hidden(self):
        view = {a['achievement'].slug: a for a in progress.achievements_view(self.character)}
        self.assertTrue(view['increvable']['secret'])
        self.assertFalse(view['premier-sang']['secret'])

    def test_page_and_menu(self):
        DailyTask.objects.update(is_active=True)
        self.client.login(username='heros', password='pass')
        page = self.client.get(reverse('rpg_progress'))
        self.assertContains(page, "Tâches du jour")
        self.assertContains(page, "Premier sang")
        self.assertContains(page, "Succès secret")
        self.assertContains(page, "🎯 Objectifs <span class=\"rpg-pill\">3</span>", html=False)

    def test_unlock_happens_when_a_page_is_shown(self):
        self.character.victories = 1
        self.character.save()
        self.client.login(username='heros', password='pass')
        self.client.get(reverse('rpg_play'))
        self.assertTrue(CharacterAchievement.objects.filter(character=self.character,
                                                            achievement__slug='premier-sang').exists())


class PanelObjectivesTests(IvakarTestCase):
    def test_sections_listed(self):
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('panel_ivakar_list', args=['succes'])), "Premier sang")
        self.assertContains(self.client.get(reverse('panel_ivakar_list', args=['quotidiennes'])),
                            "Chasser 3 monstres")
        response = self.client.post(reverse('panel_ivakar_create', args=['quotidiennes']), {
            'name': "Boire une potion", 'slug': '', 'metric': 'victories', 'goal': 1, 'reward_xp': 5,
            'reward_coins': 0, 'min_level': 1, 'weight': 1, 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('panel_ivakar_list', args=['quotidiennes']))
        # Un compteur « à vie » n'est pas proposé pour une tâche du jour.
        response = self.client.post(reverse('panel_ivakar_create', args=['quotidiennes']), {
            'name': "Monter", 'slug': '', 'metric': 'level', 'goal': 1, 'reward_xp': 0, 'reward_coins': 0,
            'min_level': 1, 'weight': 1,
        })
        self.assertEqual(response.status_code, 200)


class CatchUpTests(IvakarTestCase):
    def test_many_unlocks_make_a_single_popup(self):
        DailyTask.objects.update(is_active=False)
        self.character.victories = 30
        self.character.explorations = 60
        self.character.save()
        progress.update(self.character)
        self.assertGreater(CharacterAchievement.objects.filter(character=self.character).count(), 2)
        self.assertEqual(Notification.objects.filter(character=self.character, kind='achievement').count(), 1)
