"""Panel — section Ivakar : accès, contenu (générique + choix), héros, change, contrôles."""
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from ivakar_rpg.checks import content_problems
from ivakar_rpg.engine import character as hero
from ivakar_rpg.engine.combat import start_combat
from ivakar_rpg.models import (
    Character, Choice, Combat, Location, LocationExit, Monster, Origin, Outcome, Scene, Wound,
)
from panel.ivakar_sections import SECTIONS
from users.models import User


class IvakarPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_ivakar', verbosity=0)

    def setUp(self):
        self.staff = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.client.login(username='admin', password='pass')

    def test_staff_only(self):
        User.objects.create_user(username='membre', password='pass')
        self.client.login(username='membre', password='pass')
        self.assertRedirects(self.client.get(reverse('panel_ivakar')), reverse('home'), fetch_redirect_response=False)

    def test_all_pages_render(self):
        urls = [reverse('panel_ivakar'), reverse('panel_ivakar_heroes'), reverse('panel_ivakar_exchanges'),
                reverse('panel_ivakar_tavern')]
        for slug, config in SECTIONS.items():
            urls += [reverse('panel_ivakar_list', args=[slug]), reverse('panel_ivakar_create', args=[slug])]
            obj = config['model'].objects.first()
            if obj is not None:
                urls.append(reverse('panel_ivakar_edit', args=[slug, obj.pk]))
        choice = Choice.objects.first()
        urls += [reverse('panel_ivakar_choice_edit', args=[choice.pk]),
                 reverse('panel_ivakar_choice_create', args=[choice.scene_id])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_unknown_section(self):
        self.assertEqual(self.client.get(reverse('panel_ivakar_list', args=['nope'])).status_code, 404)

    def test_search(self):
        response = self.client.get(reverse('panel_ivakar_list', args=['monstres']), {'q': 'loup'})
        self.assertContains(response, "Loup alpha")
        self.assertNotContains(response, "Rat géant")

    def test_create_quest_with_derived_slug(self):
        response = self.client.post(reverse('panel_ivakar_create', args=['quetes']), {
            'title': "La forge éteinte", 'slug': '', 'summary': '', 'objective': '', 'reward_xp': 10,
            'reward_coins': 5, 'reward_item': '', 'order': 4,
        })
        self.assertRedirects(response, reverse('panel_ivakar_list', args=['quetes']))
        from ivakar_rpg.models import Quest
        self.assertTrue(Quest.objects.filter(slug='la-forge-eteinte').exists())

    def _location_post(self, location, **extra):
        data = {
            'name': location.name, 'slug': location.slug, 'description': location.description,
            'inn_price': location.inn_price, 'recommended_level': location.recommended_level,
            'calm_weight': location.calm_weight, 'order': location.order,
        }
        for flag in ('is_start', 'is_safe', 'has_inn', 'has_merchant'):
            if getattr(location, flag):
                data[flag] = 'on'
        exits = list(location.exits.all())
        data.update({'inline0-TOTAL_FORMS': len(exits) + 1, 'inline0-INITIAL_FORMS': len(exits),
                     'inline0-MIN_NUM_FORMS': 0, 'inline0-MAX_NUM_FORMS': 1000})
        for i, exit in enumerate(exits):
            data.update({f'inline0-{i}-id': exit.pk, f'inline0-{i}-to_location': exit.to_location_id,
                         f'inline0-{i}-label': exit.label, f'inline0-{i}-required_level': exit.required_level,
                         f'inline0-{i}-required_item': exit.required_item_id or '',
                         f'inline0-{i}-required_flag': exit.required_flag,
                         f'inline0-{i}-locked_text': exit.locked_text, f'inline0-{i}-order': exit.order})
        n = len(exits)
        data.update({f'inline0-{n}-to_location': '', f'inline0-{n}-label': '', f'inline0-{n}-required_level': 0,
                     f'inline0-{n}-order': 0})
        encounters = list(location.encounters.all())
        data.update({'inline1-TOTAL_FORMS': len(encounters), 'inline1-INITIAL_FORMS': len(encounters),
                     'inline1-MIN_NUM_FORMS': 0, 'inline1-MAX_NUM_FORMS': 1000})
        for i, enc in enumerate(encounters):
            data.update({f'inline1-{i}-id': enc.pk, f'inline1-{i}-monster': enc.monster_id,
                         f'inline1-{i}-weight': enc.weight})
        data.update(extra)
        return data

    def test_edit_location_and_add_exit(self):
        location = Location.objects.get(slug='precalm')
        before = location.exits.count()
        data = self._location_post(location, name="Précalm-la-Neuve")
        n = before
        data.update({f'inline0-{n}-to_location': Location.objects.get(slug='mine-abandonnee').pk,
                     f'inline0-{n}-label': "Raccourci", f'inline0-{n}-required_level': 3})
        response = self.client.post(reverse('panel_ivakar_edit', args=['lieux', location.pk]), data)
        self.assertRedirects(response, reverse('panel_ivakar_list', args=['lieux']))
        location.refresh_from_db()
        self.assertEqual(location.name, "Précalm-la-Neuve")
        self.assertEqual(location.exits.count(), before + 1)

    def test_new_origin_prefills_seven_characteristics(self):
        response = self.client.get(reverse('panel_ivakar_create', args=['origines']))
        self.assertEqual(response.context['formsets'][0]['formset'].total_form_count(), 7)

    def test_new_origin_on_empty_database(self):
        """En prod, aucune caractéristique n'existait avant la première origine."""
        from ivakar_rpg.models import Characteristic
        Characteristic.objects.all().delete()
        response = self.client.get(reverse('panel_ivakar_create', args=['origines']))
        self.assertEqual(response.context['formsets'][0]['formset'].total_form_count(), 7)
        self.assertContains(response, 'Constitution')

    def test_delete(self):
        monster = Monster.objects.get(slug='rat-geant')
        self.client.post(reverse('panel_ivakar_delete', args=['monstres', monster.pk]))
        self.assertFalse(Monster.objects.filter(pk=monster.pk).exists())

    def _outcome_data(self, prefix, **values):
        data = {f'{prefix}-{k}': v for k, v in {'text': '', 'xp': 0, 'coins': 0, 'hp': 0, 'wound': 0}.items()}
        data.update({f'{prefix}-{k}': v for k, v in values.items()})
        return data

    def test_create_choice_with_two_outcomes(self):
        scene = Scene.objects.get(slug='filon-cuivre')
        data = {'label': "Chercher une autre veine", 'order': 5, 'test_characteristic': Choice.objects.filter(
            test_characteristic__code='perception').first().test_characteristic_id, 'test_difficulty': 13,
            'required_level': 0, 'required_coins': 0}
        data.update(self._outcome_data('success', text="Trouvé !", coins=5))
        data.update(self._outcome_data('failure', hp=-1))
        response = self.client.post(reverse('panel_ivakar_choice_create', args=[scene.pk]), data)
        self.assertRedirects(response, reverse('panel_ivakar_edit', args=['scenes', scene.pk]))
        choice = Choice.objects.get(label="Chercher une autre veine")
        self.assertEqual(choice.scene, scene)
        self.assertEqual(choice.outcomes.get(result=Outcome.RESULT_SUCCESS).coins, 5)
        self.assertEqual(choice.outcomes.get(result=Outcome.RESULT_FAILURE).hp, -1)

    def test_untouched_failure_is_not_created(self):
        scene = Scene.objects.get(slug='filon-cuivre')
        data = {'label': "Rebrousser chemin dans la galerie", 'order': 6, 'test_difficulty': 13, 'required_level': 0, 'required_coins': 0}
        data.update(self._outcome_data('success'))
        data.update(self._outcome_data('failure'))
        self.client.post(reverse('panel_ivakar_choice_create', args=[scene.pk]), data)
        self.assertEqual(Choice.objects.get(label="Rebrousser chemin dans la galerie").outcomes.count(), 1)

    def test_drop_failure(self):
        choice = Choice.objects.filter(outcomes__result=Outcome.RESULT_FAILURE).first()
        data = {'label': choice.label, 'order': choice.order,
                'test_characteristic': choice.test_characteristic_id or '', 'test_difficulty': choice.test_difficulty,
                'required_level': 0, 'required_coins': 0, 'drop_failure': 'on'}
        data.update(self._outcome_data('success'))
        data.update(self._outcome_data('failure'))
        self.client.post(reverse('panel_ivakar_choice_edit', args=[choice.pk]), data)
        self.assertFalse(choice.outcomes.filter(result=Outcome.RESULT_FAILURE).exists())

    def test_hero_troubleshooting(self):
        player = User.objects.create_user(username='joueur', password='x')
        character = hero.create_character(player, "Brann", Origin.objects.first().pk)
        start_combat(character, Monster.objects.first())
        character.state = Character.STATE_KO
        character.hp = 0
        character.save()
        Wound.objects.create(character=character, severity=Wound.SEVERITY_SEVERE)
        url = reverse('panel_ivakar_hero', args=[character.pk])
        self.assertContains(self.client.get(url), "Brann")
        for action in ('end_combat', 'wake', 'heal', 'clear_wounds'):
            self.client.post(url, {'action': action})
        character.refresh_from_db()
        self.assertFalse(Combat.objects.filter(character=character).exists())
        self.assertEqual(character.state, Character.STATE_OK)
        self.assertEqual(character.hp, hero.max_hp(character))
        self.assertFalse(Wound.objects.filter(character=character).exists())

    def test_hero_edit_and_delete(self):
        player = User.objects.create_user(username='joueur', password='x')
        character = hero.create_character(player, "Brann", Origin.objects.first().pk)
        url = reverse('panel_ivakar_hero', args=[character.pk])
        self.client.post(url, {'action': 'save', 'name': 'Brann II', 'coins': 99, 'hp': 5, 'unspent_points': 1,
                               'location': character.location_id, 'flags': "quete_loups\n\n"})
        character.refresh_from_db()
        self.assertEqual((character.name, character.coins, character.flags), ('Brann II', 99, ['quete_loups']))
        self.client.post(url, {'action': 'delete'})
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())

    def test_sample_content_is_consistent(self):
        self.assertEqual([p for p in content_problems() if p[0] == 'danger'], [])

    def test_checks_detect_flag_typo(self):
        exit = LocationExit.objects.first()
        exit.required_flag = 'marqueur_inexistant'
        exit.save()
        self.assertTrue(any('marqueur_inexistant' in p[1] for p in content_problems()))
        self.assertContains(self.client.get(reverse('panel_ivakar')), 'marqueur_inexistant')

    def test_create_world_event(self):
        response = self.client.post(reverse('panel_ivakar_create', args=['evenements']), {
            'name': "L'Ombre d'Agasur", 'slug': '', 'description': '', 'monster': Monster.objects.first().pk,
            'location': '', 'starts_at': '2026-11-21T18:00', 'ends_at': '2026-11-28T18:00', 'hp_total': 800,
            'hp_left': '', 'hit_difficulty': 13, 'dodge_difficulty': 13, 'damage_min': 2, 'damage_max': 6,
            'cooldown_minutes': 30, 'reward_xp': 50, 'reward_coins': 20, 'top_reward_item': '',
        })
        self.assertRedirects(response, reverse('panel_ivakar_list', args=['evenements']))
        from ivakar_rpg.models import WorldEvent
        event = WorldEvent.objects.get(slug='lombre-dagasur')
        self.assertEqual((event.hp_total, event.hp_left), (800, 800))
        self.assertContains(self.client.get(reverse('panel_ivakar_list', args=['evenements'])), "800 / 800")

    def test_tavern_moderation(self):
        from ivakar_rpg.engine import social
        from ivakar_rpg.models import LocationMessage
        player = User.objects.create_user(username='bavard', password='x')
        character = hero.create_character(player, "Bavard", Origin.objects.first().pk)
        message = social.say(character, "Message à modérer")
        url = reverse('panel_ivakar_tavern')
        self.assertContains(self.client.get(url), "Message à modérer")
        self.client.post(url, {'message': message.pk, 'action': 'hide'})
        self.assertTrue(LocationMessage.objects.get().is_hidden)
        self.client.post(url, {'message': message.pk, 'action': 'delete'})
        self.assertFalse(LocationMessage.objects.exists())

    def test_menu_link(self):
        self.assertContains(self.client.get(reverse('panel_dashboard')), reverse('panel_ivakar'))
