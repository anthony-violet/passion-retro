"""Compétences : obtention par origine et niveau, usage en combat et en duel, recharge, panel."""
from django.urls import reverse

from ..engine import RpgError
from ..engine import character as hero
from ..engine import combat as fight
from ..engine import duel as duel_engine
from ..engine import skills
from ..models import Combat, Monster, Notification, Origin, Skill
from .helpers import FixedRng, IvakarTestCase
from .test_social import SocialTestCase


class SkillTests(IvakarTestCase):
    """Aldric est soldat de garnison (Force 15, Charisme 8) : Charge au niveau 1, Garde de fer au niveau 3.
    Charge : Force contre Dextérité, +1 au jet, +1D6 de dégâts, recharge 3 manches."""

    def fight(self, monster_action='feint'):
        fight.start_combat(self.character, Monster.objects.get(slug='loup-gris'), rng=FixedRng(1))
        combat = Combat.objects.get(character=self.character)
        combat.monster_action = monster_action
        combat.save()
        return combat

    def test_known_and_upcoming_follow_origin_and_level(self):
        self.assertEqual([s.slug for s in skills.known(self.character)], ['charge'])
        self.assertEqual([s.slug for s in skills.upcoming(self.character)], ['garde-de-fer'])

    def test_skill_in_combat_then_cooldown(self):
        self.fight('feint')
        # Charge 6+6+5+1 contre 1+1+3 : appuyée. Dégâts 1 + 6 + 1 (D6 de la compétence) + 1 (lourd) + 1 (appuyé)
        # = 10 → le loup (12 PV) garde 2 PV. Sa Feinte est trop lente.
        fight.act(self.character, 'skill:charge', rng=FixedRng(6, 6, 1, 1, 1, 1, 1, 1, 1))
        combat = Combat.objects.get(character=self.character)
        self.assertEqual(combat.monster_hp, 2)
        self.assertEqual(combat.skill_cooldowns, {'charge': 3})
        self.assertTrue(any(['act', "🐂 Charge"] in e['parts'] for e in combat.log))
        with self.assertRaises(RpgError):
            fight.act(self.character, 'skill:charge')

    def test_cooldown_wears_off(self):
        combat = self.fight('feint')
        combat.skill_cooldowns = {'charge': 2}
        combat.save()
        for _ in range(2):
            Combat.objects.filter(pk=combat.pk).update(monster_action='guard')
            fight.act(self.character, 'guard', rng=FixedRng(1))
        self.assertEqual(Combat.objects.get(pk=combat.pk).skill_cooldowns, {})

    def test_skill_not_yet_learned(self):
        self.fight()
        with self.assertRaises(RpgError):
            fight.act(self.character, 'skill:garde-de-fer')

    def test_healing_skill(self):
        self.character.origin = Origin.objects.get(slug='heraut')
        self.character.hp = 5
        self.character.save()
        self.fight('guard')
        # Harangue : 1D6 (3) + ⌊Charisme 8 ÷ 3⌋ (2) + 1 = 6 PV.
        fight.act(self.character, 'skill:harangue', rng=FixedRng(3, 1))
        self.assertEqual(self.reload().hp, 11)

    def test_level_up_announces_new_skill(self):
        c = self.reload()
        hero.gain_xp(c, hero.xp_for_level(3))
        c.save()
        self.assertTrue(Notification.objects.filter(character=c, kind='skill_learned',
                                                    title__contains="Garde de fer").exists())

    def test_pages(self):
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('rpg_sheet')), "Garde de fer")
        self.fight()
        page = self.client.get(reverse('rpg_play'))
        self.assertContains(page, 'value="skill:charge"')


class DuelSkillTests(SocialTestCase):
    def test_skill_in_duel(self):
        duel = duel_engine.accept(self.other, duel_engine.challenge(self.character, self.other.pk).pk)
        duel_engine.choose(self.character, duel.pk, 'skill:charge')
        duel.refresh_from_db()
        self.assertEqual(duel_engine.view_state(duel, self.character)['my_action_label'], "🐂 Charge")
        # La Charge s'écrase sur la Garde ; la riposte (1+1 contre 6+6) échoue.
        duel = duel_engine.choose(self.other, duel.pk, 'guard', rng=FixedRng(1, 1, 6, 6))
        self.assertEqual(duel.challenger_cooldowns, {'charge': 3})
        with self.assertRaises(RpgError):
            duel_engine.choose(self.character, duel.pk, 'skill:charge')


class SkillPanelTests(IvakarTestCase):
    def test_create_and_filter(self):
        self.client.login(username='heros', password='pass')
        soldier = Origin.objects.get(slug='soldat-garnison')
        self.assertContains(self.client.get(reverse('panel_ivakar_list', args=['competences'])), "Charge")
        response = self.client.post(reverse('panel_ivakar_create', args=['competences']), {
            'name': "Bouclier levé", 'slug': '', 'icon': "🛡️", 'description': "Une garde sûre.", 'kind': 'guard',
            'stat': 'constitution', 'against': 'dexterite', 'roll_bonus': 1, 'extra_dice': 0, 'flat_bonus': 0,
            'cooldown': 2, 'min_level': 2, 'origins': [soldier.pk], 'order': 0, 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('panel_ivakar_list', args=['competences']))
        skill = Skill.objects.get(slug='bouclier-leve')
        self.assertEqual(list(skill.origins.all()), [soldier])
        page = self.client.get(reverse('panel_ivakar_list', args=['competences']), {'origins': soldier.pk})
        self.assertContains(page, "Bouclier levé")
        self.assertNotContains(page, "Tir visé")
        self.assertEqual(self.client.get(reverse('panel_ivakar_create', args=['competences']),
                                         {'origins': soldier.pk}).status_code, 200)
