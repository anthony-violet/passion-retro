"""PNJ : présence dans les lieux, dialogue qui évolue avec les marqueurs, écrans et panel."""
from django.urls import reverse

from ..checks import content_problems
from ..engine import RpgError, npcs, progress
from ..models import Location, Npc, NpcDialogue, Scene
from .helpers import IvakarTestCase


class NpcTests(IvakarTestCase):
    def setUp(self):
        super().setUp()
        self.maela = Npc.objects.get(slug='maela')

    def test_present_at_location_with_dialogue(self):
        here = npcs.npcs_here(self.character)
        self.assertEqual([(n.slug, d.scene.slug) for n, d in here], [('maela', 'maela-comptoir')])

    def test_dialogue_follows_flags(self):
        self.character.flags = ['quete_loups']
        self.assertEqual(npcs.dialogue_for(self.character, self.maela).scene.slug, 'maela-inquiete')
        self.character.flags = ['quete_loups', 'loups_vaincus']
        self.assertEqual(npcs.dialogue_for(self.character, self.maela).scene.slug, 'maela-reconnaissante')

    def test_talk_opens_the_scene_and_remembers_the_npc(self):
        npcs.talk(self.character, self.maela.pk)
        c = self.reload()
        self.assertEqual(c.scene.slug, 'maela-comptoir')
        self.assertEqual(c.npcs_met, [self.maela.pk])
        with self.assertRaises(RpgError):  # déjà dans une scène
            npcs.talk(c, self.maela.pk)

    def test_cannot_talk_to_someone_elsewhere(self):
        with self.assertRaises(RpgError):
            npcs.talk(self.character, Npc.objects.get(slug='tobald').pk)

    def test_nothing_to_say(self):
        NpcDialogue.objects.filter(npc=self.maela).delete()
        self.assertIsNone(npcs.npcs_here(self.character)[0][1])
        with self.assertRaises(RpgError):
            npcs.talk(self.character, self.maela.pk)

    def test_meeting_npcs_counts_for_achievements(self):
        self.character.npcs_met = [1, 2]
        self.character.save()
        progress.update(self.character)
        self.assertTrue(self.character.achievements.filter(achievement__slug='visage-connu').exists())

    def test_location_and_scene_pages(self):
        self.client.login(username='heros', password='pass')
        page = self.client.get(reverse('rpg_play'))
        self.assertContains(page, "Maela")
        self.assertContains(page, reverse('rpg_talk', args=[self.maela.pk]))
        self.assertContains(page, "ivakar/pnj/maela.svg")
        self.client.post(reverse('rpg_talk', args=[self.maela.pk]))
        page = self.client.get(reverse('rpg_play'))
        self.assertContains(page, "Au comptoir de Maela")
        self.assertContains(page, "rpg-speaker")

    def test_unknown_portrait_falls_back(self):
        npc = Npc.objects.create(slug='sans-visage', name="Sans visage")
        self.assertTrue(npc.visual_url.endswith('ivakar/pnj/inconnu.svg'))


class NpcContentTests(IvakarTestCase):
    def test_npc_scenes_are_not_reported_as_unreachable(self):
        messages = [m for _, m, _, _ in content_problems()]
        self.assertFalse([m for m in messages if 'maela' in m.lower() or 'tobald' in m.lower()], messages)

    def test_npc_without_dialogue_or_place_is_reported(self):
        Npc.objects.create(slug='perdu', name="Perdu")
        messages = " ".join(m for _, m, _, _ in content_problems())
        self.assertIn("« Perdu » n'est placé dans aucun lieu", messages)
        self.assertIn("« Perdu » n'a aucun dialogue", messages)

    def test_tree_lists_npcs_as_entry_points(self):
        from .. import scenario_tree
        groups, orphans = scenario_tree.build()
        precalm = next(g for g in groups if g['location'].slug == 'precalm')
        self.assertEqual([e['npc'].slug for e in precalm['npcs']], ['maela'])
        self.assertEqual([d['node']['scene'].slug for d in precalm['npcs'][0]['dialogues']],
                         ['maela-comptoir', 'maela-inquiete', 'maela-reconnaissante'])
        self.assertNotIn('ermite-tobald', [n['scene'].slug for n in orphans])

    def test_panel(self):
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('panel_ivakar_list', args=['pnj'])), "Tobald")
        maela = Npc.objects.get(slug='maela')
        self.assertContains(self.client.get(reverse('panel_ivakar_edit', args=['pnj', maela.pk])), "Dialogues")
        self.assertContains(self.client.get(reverse('panel_ivakar_tree')), "aubergiste du Pot Cassé")
        precalm = Location.objects.get(slug='precalm')
        scene = Scene.objects.get(slug='maela-comptoir')
        response = self.client.post(reverse('panel_ivakar_create', args=['pnj']), {
            'name': "Garde du pont", 'slug': '', 'role': "garde", 'description': '', 'locations': [precalm.pk],
            'order': 0, 'is_active': 'on',
            'inline0-TOTAL_FORMS': 1, 'inline0-INITIAL_FORMS': 0, 'inline0-MIN_NUM_FORMS': 0,
            'inline0-MAX_NUM_FORMS': 1000,
            'inline0-0-scene': scene.pk, 'inline0-0-label': "Saluer", 'inline0-0-order': 1,
            'inline0-0-min_level': 0, 'inline0-0-required_flag': '', 'inline0-0-forbidden_flag': '',
        })
        self.assertRedirects(response, reverse('panel_ivakar_list', args=['pnj']))
        garde = Npc.objects.get(slug='garde-du-pont')
        self.assertEqual(garde.dialogues.get().label, "Saluer")
