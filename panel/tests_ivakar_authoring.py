"""Panel Ivakar : création en fenêtre, pré-remplissage, « Utilisé dans », scène sur une page, ébauches,
arbre éditable et assistant de quête."""
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from ivakar_rpg.checks import content_problems
from ivakar_rpg.engine import npcs
from ivakar_rpg.models import Choice, Item, Location, Monster, Npc, NpcDialogue, Outcome, Quest, Scene
from panel.ivakar_sections import SECTIONS, ChoiceForm, OutcomeForm
from users.models import User


def form_data(form):
    """Données d'envoi d'un formulaire non lié, telles que le navigateur les enverrait."""
    data = {}
    for name, field in form.fields.items():
        value = form[name].value()
        key = form.add_prefix(name)
        if isinstance(value, bool):
            if value:
                data[key] = 'on'
        elif isinstance(value, (list, tuple)):
            data[key] = [str(v) for v in value]
        elif value is None:
            data[key] = ''
        elif key.endswith('-image') or key == 'image':
            continue
        else:
            data[key] = str(value)
    return data


class AuthoringTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_ivakar', verbosity=0)

    def setUp(self):
        User.objects.create_user(username='auteur', password='pass', is_staff=True)
        self.client.login(username='auteur', password='pass')


class PopupTests(AuthoringTestCase):
    def test_related_lists_get_create_and_edit_links(self):
        scene = Scene.objects.get(slug='taniere-loups')
        choice = scene.choices.first()
        page = self.client.get(reverse('panel_ivakar_edit', args=['scenes', scene.pk])).content.decode()
        self.assertIn('data-ivk-related="monstres"', page)
        self.assertIn(f'data-ivk-create-url="{reverse("panel_ivakar_create", args=["monstres"])}"', page)
        self.assertIn(f'name="ch{choice.pk}-label"', page)
        self.assertIn('ivakar_panel.js', page)

    def test_popup_create_prefills_and_reports_back(self):
        precalm = Location.objects.get(slug='precalm')
        page = self.client.get(reverse('panel_ivakar_create', args=['scenes']),
                               {'popup': 1, 'location': precalm.pk, 'explore_weight': 2})
        self.assertNotContains(page, 'panel-sidebar')
        self.assertContains(page, f'<option value="{precalm.pk}" selected>')
        form = SECTIONS['scenes']['form'](initial={'location': precalm.pk})
        data = form_data(form)
        data.update({'title': "La fontaine", 'text': "De l'eau claire."})
        response = self.client.post(reverse('panel_ivakar_create', args=['scenes']) + '?popup=1', data)
        scene = Scene.objects.get(title="La fontaine")
        self.assertContains(response, '"type": "ivakar-saved"')
        self.assertContains(response, f'"id": {scene.pk}')
        self.assertEqual(scene.location, precalm)

    def test_flags_are_suggested(self):
        page = self.client.get(reverse('panel_ivakar_create', args=['scenes']))
        self.assertContains(page, '<datalist id="ivk-flags">')
        self.assertContains(page, '<option value="quete_loups">')
        self.assertContains(page, 'list="ivk-flags"')


class UsageTests(AuthoringTestCase):
    def test_item_shows_where_it_is_used(self):
        croc = Item.objects.get(slug='croc-alpha')
        page = self.client.get(reverse('panel_ivakar_edit', args=['objets', croc.pk]))
        self.assertContains(page, "Utilisé dans")
        self.assertContains(page, "Donné — « Le silence de la tanière")
        self.assertContains(page, "Exigé par le choix")

    def test_monster_and_npc(self):
        loup = Monster.objects.get(slug='loup-alpha')
        self.assertContains(self.client.get(reverse('panel_ivakar_edit', args=['monstres', loup.pk])), "Combat —")
        maela = Npc.objects.get(slug='maela')
        self.assertContains(self.client.get(reverse('panel_ivakar_edit', args=['pnj', maela.pk])),
                            "Dialogue « Au comptoir de Maela »")


class ScenePageTests(AuthoringTestCase):
    def scene_data(self, scene):
        data = form_data(SECTIONS['scenes']['form'](instance=scene))
        for choice in scene.choices.all():
            outcomes = {o.result: o for o in choice.outcomes.all()}
            data.update(form_data(ChoiceForm(prefix=f'ch{choice.pk}', instance=choice)))
            data.update(form_data(OutcomeForm(prefix=f'ch{choice.pk}-s', instance=outcomes.get('success'))))
            data.update(form_data(OutcomeForm(prefix=f'ch{choice.pk}-f', instance=outcomes.get('failure'))))
        data['new_choices'] = '0'
        return data

    def test_edit_add_and_delete_choices_on_one_page(self):
        scene = Scene.objects.get(slug='puits-ancien')
        scrutiny, leave = scene.choices.order_by('order')
        data = self.scene_data(scene)
        data[f'ch{scrutiny.pk}-label'] = "Scruter longuement le fond du puits"
        data[f'ch{leave.pk}-delete'] = 'on'
        new = form_data(ChoiceForm(prefix='new0'))
        new.update(form_data(OutcomeForm(prefix='new0-s')))
        new.update(form_data(OutcomeForm(prefix='new0-f')))
        new.update({'new0-label': "Descendre dans le puits", 'new0-order': '3',
                    'new0-s-new_next_scene': "Au fond du puits"})
        data.update(new)
        data['new_choices'] = '1'
        response = self.client.post(reverse('panel_ivakar_edit', args=['scenes', scene.pk]), data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:3000])
        labels = set(scene.choices.values_list('label', flat=True))
        self.assertEqual(labels, {"Scruter longuement le fond du puits", "Descendre dans le puits"})
        stub = Scene.objects.get(title="Au fond du puits")
        self.assertEqual((stub.text, stub.location), ('', scene.location))
        self.assertEqual(Outcome.objects.get(choice__label="Descendre dans le puits").next_scene, stub)

    def test_untouched_new_block_is_ignored(self):
        scene = Scene.objects.get(slug='puits-ancien')
        data = self.scene_data(scene)
        data.update(form_data(ChoiceForm(prefix='new0')))
        data.update(form_data(OutcomeForm(prefix='new0-s')))
        data.update(form_data(OutcomeForm(prefix='new0-f')))
        data['new_choices'] = '1'
        response = self.client.post(reverse('panel_ivakar_edit', args=['scenes', scene.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(scene.choices.count(), 2)

    def test_stub_is_reported_and_tagged(self):
        Scene.objects.create(slug='vide', title="Vide", text='', location=Location.objects.get(slug='precalm'),
                             explore_weight=1)
        self.assertTrue(any("« Vide » est une ébauche" in m for _, m, _, _ in content_problems()))
        self.assertContains(self.client.get(reverse('panel_ivakar_tree')), "ébauche à compléter")

    def test_both_existing_and_new_next_scene_is_refused(self):
        form = OutcomeForm(data={'new_next_scene': "Nouvelle", 'next_scene': Scene.objects.first().pk,
                                 'xp': 0, 'coins': 0, 'hp': 0, 'wound': 0})
        self.assertFalse(form.is_valid())
        self.assertIn('new_next_scene', form.errors)


class TreeWorkshopTests(AuthoringTestCase):
    def test_branch_scene_creates_and_links_a_stub(self):
        choice = Choice.objects.get(scene__slug='puits-ancien', label__startswith="Passer")
        response = self.client.post(reverse('panel_ivakar_branch_scene', args=[choice.pk, 'success']),
                                    {'title': "Sur le chemin", 'lieu': ''})
        stub = Scene.objects.get(title="Sur le chemin")
        self.assertRedirects(response, reverse('panel_ivakar_tree') + f'#scene-{stub.pk}', fetch_redirect_response=False)
        self.assertEqual(choice.outcomes.get(result='success').next_scene, stub)
        # Une branche déjà reliée n'est pas écrasée.
        self.client.post(reverse('panel_ivakar_branch_scene', args=[choice.pk, 'success']), {'title': "Autre"})
        self.assertFalse(Scene.objects.filter(title="Autre").exists())

    def test_tree_offers_inline_tools(self):
        page = self.client.get(reverse('panel_ivakar_tree'))
        self.assertContains(page, "Scène à découvrir ici")
        self.assertContains(page, "data-ivk-popup")
        self.assertContains(page, 'placeholder="＋ Scène suivante (titre)"')

    def test_staff_only(self):
        self.client.logout()
        choice = Choice.objects.first()
        self.client.post(reverse('panel_ivakar_branch_scene', args=[choice.pk, 'success']), {'title': "X"})
        self.assertFalse(Scene.objects.filter(title="X").exists())


class QuestWizardTests(AuthoringTestCase):
    def test_wizard_builds_a_playable_chain(self):
        from ivakar_rpg.engine import character as hero
        from ivakar_rpg.engine import scenes as scene_engine
        from ivakar_rpg.models import CharacterQuest, Origin

        precalm = Location.objects.get(slug='precalm')
        lisiere = Location.objects.get(slug='lisiere')
        response = self.client.post(reverse('panel_ivakar_quest_wizard'), {
            'title': "La bague perdue", 'summary': "", 'objective': "Retrouver la bague à la lisière",
            'npc': '', 'new_npc_name': "Hugues", 'new_npc_role': "meunier", 'giver_location': precalm.pk,
            'offer_text': "« J'ai perdu ma bague à la lisière. »", 'accept_label': "Promettre de la retrouver",
            'objective_location': lisiere.pk, 'objective_title': "Un éclat dans l'herbe",
            'objective_text': "Quelque chose brille.", 'objective_action': "Ramasser la bague", 'monster': '',
            'return_text': "« Ma bague ! Merci. »", 'reward_xp': 20, 'reward_coins': 10, 'reward_item': '',
        })
        self.assertRedirects(response, reverse('panel_ivakar_tree') + f'?lieu={precalm.pk}',
                             fetch_redirect_response=False)
        quest = Quest.objects.get(title="La bague perdue")
        hugues = Npc.objects.get(name="Hugues")
        self.assertEqual(NpcDialogue.objects.filter(npc=hugues).count(), 3)

        user = User.objects.create_user(username='joueur', password='pass', is_staff=True)
        c = hero.create_character(user, "Lise", Origin.objects.get(slug='eclaireur').pk)
        self.assertEqual(npcs.dialogue_for(c, hugues).scene.title, "La bague perdue : la demande")
        npcs.talk(c, hugues.pk)
        c.refresh_from_db()
        scene_engine.choose(c, Choice.objects.get(scene=c.scene, label="Promettre de la retrouver").pk)
        c.refresh_from_db()
        self.assertTrue(CharacterQuest.objects.filter(character=c, quest=quest).exists())
        self.assertEqual(npcs.dialogue_for(c, hugues).scene.title, "La bague perdue : en attente")
        goal = Scene.objects.get(title="Un éclat dans l'herbe")
        c.scene = goal
        c.save()
        scene_engine.choose(c, Choice.objects.get(scene=goal, label="Ramasser la bague").pk)
        c.refresh_from_db()
        self.assertEqual(npcs.dialogue_for(c, hugues).scene.title, "La bague perdue : le rapport")
        c.location = precalm
        c.save()
        npcs.talk(c, hugues.pk)
        c.refresh_from_db()
        scene_engine.choose(c, Choice.objects.get(scene=c.scene, label="Faire ton rapport").pk)
        c.refresh_from_db()
        self.assertEqual(CharacterQuest.objects.get(character=c, quest=quest).status, CharacterQuest.STATUS_DONE)
        self.assertIsNone(npcs.dialogue_for(c, hugues))

    def test_wizard_requires_a_giver(self):
        response = self.client.post(reverse('panel_ivakar_quest_wizard'), {'title': "Sans donneur"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisis un PNJ")

    def test_existing_npc_keeps_old_dialogues_after(self):
        from panel.ivakar_wizard import build_quest
        maela = Npc.objects.get(slug='maela')
        before = list(NpcDialogue.objects.filter(npc=maela).values_list('scene__slug', flat=True))
        build_quest({'title': "Le tonneau", 'summary': '', 'objective': "Trouver un tonneau", 'npc': maela,
                     'giver_location': None, 'offer_text': "x", 'accept_label': "Oui",
                     'objective_location': Location.objects.get(slug='lisiere'), 'objective_title': "Le tonneau",
                     'objective_text': "y", 'objective_action': "Prendre", 'monster': Monster.objects.first(),
                     'return_text': "z", 'reward_xp': 0, 'reward_coins': 0, 'reward_item': None})
        ordered = list(NpcDialogue.objects.filter(npc=maela).values_list('scene__slug', flat=True))
        self.assertEqual(ordered[3:], before)
        self.assertTrue(Scene.objects.filter(title="Le tonneau : après le combat").exists())
