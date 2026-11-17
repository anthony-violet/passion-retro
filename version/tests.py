import importlib
import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from users.models import User
from version.models import HistoryVersion

move_migration = importlib.import_module('version.migrations.0003_move_leading_image')


def png_file(name='capture.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def make_version(num, name, days_ago=0, **extra):
    version = HistoryVersion.objects.create(num_version=num, name=name, content=extra.pop('content', 'Texte'), **extra)
    HistoryVersion.objects.filter(pk=version.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    version.refresh_from_db()
    return version


class FooterVersionTest(TestCase):
    def test_footer_shows_latest_created_version(self):
        make_version('1.1', 'Ancienne', days_ago=30)
        make_version('1.3', 'Récente', days_ago=1)
        make_version('1.2', 'Entre les deux', days_ago=10)
        response = self.client.get(reverse('history_versions_home'))
        self.assertContains(response, 'Version 1.3 <a href="/version/history">Historique</a>', html=False)

    def test_footer_without_version(self):
        response = self.client.get(reverse('history_versions_home'))
        self.assertNotContains(response, '. Version ')
        self.assertContains(response, 'Historique</a>')


class HistoryPageTest(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def test_entries_alternate_image_side_newest_first(self):
        with override_settings(MEDIA_ROOT=self.media):
            make_version('1.1', 'Première', days_ago=3, image=png_file())
            make_version('1.2', 'Sans image', days_ago=2)
            make_version('1.3', 'Troisième', days_ago=1, image=png_file())
            response = self.client.get(reverse('history_versions_home'))
        html = response.content.decode()
        # 1re entrée (impaire) : image à droite ; 3e entrée (impaire aussi) : image à droite.
        self.assertLess(html.index('Troisième'), html.index('Sans image'))
        self.assertLess(html.index('Sans image'), html.index('Première'))
        self.assertIn('version-entry has-image image-right" id="version-13"', html)
        self.assertIn('version-entry " id="version-12"', html)
        self.assertIn('version-entry has-image image-right" id="version-11"', html)

    def test_even_entry_has_image_on_the_left(self):
        with override_settings(MEDIA_ROOT=self.media):
            make_version('1.1', 'Paire', days_ago=2, image=png_file())
            make_version('1.2', 'Impaire', days_ago=1)
            response = self.client.get(reverse('history_versions_home'))
        self.assertContains(response, 'version-entry has-image image-left" id="version-11"')

    def test_list_in_content_is_not_inside_a_paragraph(self):
        make_version('1.0', 'Liste', content='Intro :\n[list][*]Un[*]Deux[/list]\nSuite [b]en gras[/b].')
        response = self.client.get(reverse('history_versions_home'))
        self.assertContains(response, '<div class="version-content">Intro :')
        self.assertNotContains(response, '<p>Intro')


class PanelVersionImageTest(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.staff = User.objects.create_user(username='modo', email='m@test.com', password='testpass123', is_staff=True)
        self.client.login(username='modo', password='testpass123')

    def test_create_without_image(self):
        response = self.client.post(reverse('panel_version_create'), {'num_version': '1.4', 'name': 'Sans capture', 'content': 'Texte'})
        self.assertRedirects(response, reverse('panel_version'))
        self.assertFalse(HistoryVersion.objects.get(num_version='1.4').image)

    def test_create_replace_and_remove_image(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.client.post(reverse('panel_version_create'), {
                'num_version': '1.4', 'name': 'Avec capture', 'content': 'Texte', 'image': png_file(),
            })
            version = HistoryVersion.objects.get(num_version='1.4')
            self.assertTrue(version.image.name.startswith('versions/'))

            self.client.post(reverse('panel_version_edit', args=[version.pk]), {
                'num_version': '1.4', 'name': 'Avec capture', 'content': 'Texte modifié',
            })
            version.refresh_from_db()
            self.assertTrue(version.image, "Modifier sans nouveau fichier garde la capture")

            self.client.post(reverse('panel_version_edit', args=[version.pk]), {
                'num_version': '1.4', 'name': 'Avec capture', 'content': 'Texte', 'remove_image': 'on',
            })
            version.refresh_from_db()
            self.assertFalse(version.image)

    def test_rejects_non_image_file(self):
        response = self.client.post(reverse('panel_version_create'), {
            'num_version': '1.4', 'name': 'Mauvais fichier',
            'image': SimpleUploadedFile('notes.txt', b'pas une image', content_type='text/plain'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(HistoryVersion.objects.exists())


class MoveLeadingImageMigrationTest(TestCase):
    def test_split_leading_image(self):
        path, content = move_migration.split_leading_image('[img]/media/galleries/1/a.png[/img]\r\nTexte [b]gras[/b]')
        self.assertEqual(path, 'galleries/1/a.png')
        self.assertEqual(content, 'Texte [b]gras[/b]')

    def test_keeps_content_without_leading_media_image(self):
        for content in ('Texte puis [img]/media/a.png[/img]', '[img]https://ailleurs.example/a.png[/img] Texte', ''):
            self.assertEqual(move_migration.split_leading_image(content), (None, content))
