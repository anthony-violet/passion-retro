"""Règles validées : résolution, caractéristiques, progression, blessures."""
from django.test import SimpleTestCase

from users.models import User

from ..engine import RpgError
from ..engine import character as hero
from ..engine import wounds
from ..engine.rules import CHARACTERISTICS, aggravation_check, bonus, resolve
from ..models import Character, Combat, Location, Origin, Wound
from .helpers import FixedRng, IvakarTestCase


class ResolutionTests(SimpleTestCase):
    def test_bonus_is_floor_of_third(self):
        self.assertEqual([bonus(v) for v in (1, 2, 3, 5, 6, 14, 20, 92, 100)], [0, 0, 1, 1, 2, 4, 6, 30, 33])

    def test_two_d6_plus_bonus_against_threshold(self):
        result = resolve(14, 13, FixedRng(3, 5))  # 8 + 4 = 12
        self.assertEqual((result.total, result.success), (12, False))
        result = resolve(14, 10, FixedRng(3, 5))
        self.assertTrue(result.success)

    def test_success_when_total_equals_threshold(self):
        result = resolve(12, 16, FixedRng(6, 6))  # 12 + 4 = 16
        self.assertTrue(result.success)

    def test_no_natural_success_or_failure(self):
        self.assertFalse(resolve(0, 13, FixedRng(6, 6)).success)  # 12 < 13 : pas de réussite automatique
        self.assertTrue(resolve(60, 13, FixedRng(1, 1)).success)  # 2 + 20 >= 13 : pas d'échec automatique

    def test_seven_characteristics(self):
        self.assertEqual(list(CHARACTERISTICS), ['force', 'constitution', 'dexterite', 'perception',
                                                 'intelligence', 'mental', 'charisme'])


class AggravationTests(SimpleTestCase):
    def test_coefficients(self):
        self.assertEqual(aggravation_check(10, Wound.SEVERITY_LIGHT, FixedRng(1)).threshold, 50)
        self.assertEqual(aggravation_check(10, Wound.SEVERITY_MODERATE, FixedRng(1)).threshold, 40)
        self.assertEqual(aggravation_check(10, Wound.SEVERITY_SEVERE, FixedRng(1)).threshold, 30)

    def test_d10_times_ten_against_threshold(self):
        self.assertTrue(aggravation_check(10, Wound.SEVERITY_LIGHT, FixedRng(5)).stable)  # 50 <= 50
        self.assertFalse(aggravation_check(10, Wound.SEVERITY_LIGHT, FixedRng(6)).stable)  # 60 > 50


class CreationAndProgressionTests(IvakarTestCase):
    def test_values_come_from_origin(self):
        expected = {row.characteristic.code: row.value for row in self.origin.values.select_related('characteristic')}
        self.assertEqual(hero.stat_values(self.character), expected)
        self.assertTrue(all(1 <= v <= 20 for v in expected.values()))

    def test_origins_have_no_fixed_total(self):
        totals = {sum(row.value for row in origin.values.all()) for origin in Origin.objects.all()}
        self.assertGreater(len(totals), 1)

    def test_starting_state(self):
        c = self.reload()
        self.assertEqual(c.level, 1)
        self.assertEqual(c.location.slug, 'precalm')
        self.assertEqual(c.hp, hero.max_hp(c))
        self.assertEqual(c.state, Character.STATE_OK)

    def test_one_hero_per_member(self):
        with self.assertRaises(RpgError):
            hero.create_character(self.user, "Bis", self.origin.pk)

    def test_origin_is_required(self):
        other = User.objects.create_user(username='autre', password='x')
        with self.assertRaises(RpgError):
            hero.create_character(other, "Sans origine", None)

    def test_level_up_gives_three_points_and_nothing_automatic(self):
        before = hero.stat_values(self.character)
        c = self.reload()
        gained = hero.gain_xp(c, hero.xp_for_level(3))
        c.save()
        c = self.reload()
        self.assertEqual((gained, c.level, c.unspent_points), (2, 3, 6))
        self.assertEqual(hero.stat_values(c), before)

    def test_max_level_is_25(self):
        c = self.reload()
        hero.gain_xp(c, 10 ** 7)
        c.save()
        c = self.reload()
        self.assertEqual((c.level, c.unspent_points), (25, 72))

    def test_spend_point_and_absolute_cap(self):
        self.character.unspent_points = 2
        self.character.save()
        hero.spend_point(self.character, 'force')
        self.assertEqual(hero.stat_values(self.character)['force'], 16)
        self.set_stat('force', 100)
        with self.assertRaises(RpgError):
            hero.spend_point(self.character, 'force')


class WoundTests(IvakarTestCase):
    def test_context_risk_uses_force(self):
        Wound.objects.create(character=self.character, severity=Wound.SEVERITY_LIGHT)
        self.set_stat('force', 10)
        self.set_stat('mental', 20)
        wounds.context_check(self.character, FixedRng(6))  # 60 > 10 × 5
        self.assertEqual(Wound.objects.get().severity, Wound.SEVERITY_MODERATE)

    def test_time_risk_uses_mental(self):
        Wound.objects.create(character=self.character, severity=Wound.SEVERITY_MODERATE)
        self.set_stat('force', 1)
        self.set_stat('mental', 20)
        wounds.time_check(self.character, FixedRng(8))  # 80 <= 20 × 4
        self.assertEqual(Wound.objects.get().severity, Wound.SEVERITY_MODERATE)

    def test_zero_hp_is_ko_not_death(self):
        c = self.reload()
        self.set_stat('constitution', 9)
        knocked = hero.change_hp(c, -1000, rng=FixedRng(1, 1))  # 2 + 3 < 13 → blessure grave
        c.save()
        c = self.reload()
        self.assertTrue(knocked)
        self.assertEqual(c.state, Character.STATE_KO)
        self.assertEqual(Wound.objects.get(character=c).severity, Wound.SEVERITY_SEVERE)
        self.assertTrue(Character.objects.filter(pk=c.pk).exists())

    def test_wake_up_after_ko(self):
        c = self.reload()
        c.location = Location.objects.get(slug='lisiere')
        hero.change_hp(c, -1000, rng=FixedRng(6, 6))
        c.save()
        wounds.wake_up(c)
        c = self.reload()
        self.assertEqual((c.state, c.location.slug), (Character.STATE_OK, 'precalm'))
        self.assertGreater(c.hp, 0)
        self.assertFalse(Combat.objects.filter(character=c).exists())

    def test_inn_treats_wounds_by_one_degree(self):
        Wound.objects.create(character=self.character, severity=Wound.SEVERITY_LIGHT)
        Wound.objects.create(character=self.character, severity=Wound.SEVERITY_SEVERE)
        hero.rest(self.character)
        self.assertEqual(list(Wound.objects.values_list('severity', flat=True)), [Wound.SEVERITY_MODERATE])
