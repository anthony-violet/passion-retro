"""Illustrations et carte du monde."""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from users.models import User

from ..engine import world
from ..engine.worldmap import map_for
from ..models import Item, Location, LocationExit, Monster, Scene, WorldMap
from .helpers import IvakarTestCase

PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4'
       b'\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82')


class VisualTests(IvakarTestCase):
    def test_builtin_visuals_exist_for_sample_content(self):
        for model in (Location, Monster, Item):
            for obj in model.objects.all():
                self.assertTrue(obj.visual_url.endswith(f'{obj.slug}.svg'), obj)

    def test_scene_falls_back_on_location(self):
        scene = Scene.objects.get(slug='pot-casse')
        self.assertEqual(scene.visual_url, scene.location.visual_url)

    def test_default_map_background(self):
        self.assertTrue(WorldMap.current().background_url.endswith('parchemin.svg'))

    def test_uploaded_image_wins(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            monster = Monster.objects.get(slug='loup-gris')
            monster.image = SimpleUploadedFile('loup.png', PNG, content_type='image/png')
            monster.save()
            self.assertIn('/media/ivakar/', monster.visual_url)


class MapTests(IvakarTestCase):
    def names(self, data):
        return {m['location'].slug for m in data['markers']}

    def test_fog_of_war(self):
        self.assertEqual(self.names(map_for(self.reload())), {'precalm', 'lisiere'})

    def test_travel_reveals(self):
        exit = LocationExit.objects.get(from_location__slug='precalm', to_location__slug='lisiere')
        world.move(self.character, exit.pk)
        names = self.names(map_for(self.reload()))
        self.assertTrue({'foret-murmures', 'mine-abandonnee'} <= names)
        self.assertNotIn('ruines-vel-ithar', names)

    def test_reachable_neighbour_and_current(self):
        markers = {m['location'].slug: m for m in map_for(self.reload())['markers']}
        self.assertTrue(markers['precalm']['current'])
        self.assertIsNotNone(markers['lisiere']['exit'])
        self.assertIsNone(markers['lisiere']['lock_reason'])

    def test_unplaced_locations_are_hidden(self):
        Location.objects.filter(slug='lisiere').update(map_x=None)
        self.assertNotIn('lisiere', self.names(map_for(self.reload())))

    def test_staff_sees_everything(self):
        self.assertEqual(len(map_for(None)['markers']), Location.objects.count())

    def test_map_page(self):
        self.client.login(username='heros', password='pass')
        response = self.client.get(reverse('rpg_map'))
        self.assertContains(response, 'La Lisière brumeuse')
        self.assertNotContains(response, 'Les Ruines de Vel-Ithar')
        self.assertContains(response, reverse('rpg_move', args=[
            LocationExit.objects.get(from_location__slug='precalm', to_location__slug='lisiere').pk]))

    def test_marker_positions_are_valid_css(self):
        """Le français écrit 25,0 : les positions doivent rester au format CSS (25.0)."""
        self.client.login(username='heros', password='pass')
        Location.objects.filter(slug='precalm').update(map_x=255, map_y=857)
        response = self.client.get(reverse('rpg_map'))
        self.assertContains(response, 'left: 25.5%; top: 85.7%')

    def test_play_page_shows_illustration(self):
        self.client.login(username='heros', password='pass')
        self.assertContains(self.client.get(reverse('rpg_play')), 'ivakar/lieux/precalm.svg')


class PanelMapTests(IvakarTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='heros', password='pass')  # membre du staff (voir helpers)

    def test_save_positions(self):
        loc = Location.objects.get(slug='mine-abandonnee')
        self.client.post(reverse('panel_ivakar_map'), {'action': 'positions', f'x_{loc.pk}': 123,
                                                       f'y_{loc.pk}': 2000})
        loc.refresh_from_db()
        self.assertEqual((loc.map_x, loc.map_y), (123, 1000))

    def test_place_and_unplace(self):
        loc = Location.objects.get(slug='mine-abandonnee')
        self.client.post(reverse('panel_ivakar_map'), {'action': 'unplace', 'location': loc.pk})
        loc.refresh_from_db()
        self.assertIsNone(loc.map_x)
        self.client.post(reverse('panel_ivakar_map'), {'action': 'place', 'location': loc.pk})
        loc.refresh_from_db()
        self.assertEqual((loc.map_x, loc.map_y), (500, 500))

    def test_background_upload_and_reset(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            self.client.post(reverse('panel_ivakar_map'), {
                'action': 'background', 'image': SimpleUploadedFile('fond.png', PNG, content_type='image/png')})
            self.assertIn('/media/ivakar/carte/', WorldMap.current().background_url)
            self.client.post(reverse('panel_ivakar_map'), {'action': 'reset_background'})
            self.assertTrue(WorldMap.current().background_url.endswith('parchemin.svg'))

    def test_panel_map_page(self):
        response = self.client.get(reverse('panel_ivakar_map'))
        self.assertContains(response, 'data-marker')
        self.assertContains(response, 'Les Ruines de Vel-Ithar')

    def test_members_cannot_edit_map(self):
        User.objects.create_user(username='membre', password='pass')
        self.client.login(username='membre', password='pass')
        loc = Location.objects.get(slug='mine-abandonnee')
        self.client.post(reverse('panel_ivakar_map'), {'action': 'positions', f'x_{loc.pk}': 1, f'y_{loc.pk}': 1})
        loc.refresh_from_db()
        self.assertNotEqual(loc.map_x, 1)
