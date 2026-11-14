import shutil
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class GalleryBasicTest(TestCase):
    def test_gallery_app_exists(self):
        from django.apps import apps

        self.assertTrue(apps.is_installed("gallery"))


class GalleryViewsTest(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)

        self.user = User.objects.create_user(
            username="galleryuser",
            email="gallery@test.com",
            password="testpass123",
            active=True,
        )
        self.client.force_login(self.user)
        self.user_dir = Path(self.media_root) / "galleries" / str(self.user.id)

    def test_gallery_page_is_accessible(self):
        response = self.client.get(reverse("home_gallery"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gallery/index.html")

    def test_gallery_embed_is_accessible(self):
        response = self.client.get(reverse("gallery_embed"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gallery/home.html")

    def test_gallery_page_renders_inline_import_form(self):
        response = self.client.get(reverse("home_gallery"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gallery/_import_form.html")
        self.assertContains(response, "gallery-import-panel")
        self.assertContains(response, 'type="file"')

    def test_import_panel_is_outside_images_loop(self):
        folder = self.user_dir / "Dossier"
        folder.mkdir(parents=True)
        (folder / "photo.jpg").write_bytes(b"fake-image-content")

        response = self.client.get(reverse("home_gallery") + "?folder=Dossier")
        html = response.content.decode()

        self.assertLess(html.index("gallery-import-panel"), html.index("gallery-layout"))
        self.assertEqual(html.count("data-gallery-import-panel"), 1)

    def test_import_popup_form_action_preserves_popup(self):
        response = self.client.get(reverse("import") + "?folder=Mes%20images&popup=1")
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("popup=1", html)
        self.assertIn("folder=Mes", html)

    def test_import_popup_is_minimal(self):
        response = self.client.get(reverse("import") + "?popup=1")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gallery/import_popup.html")
        self.assertTemplateNotUsed(response, "layout.html")
        self.assertContains(response, 'type="file"')

    def test_import_popup_post_success_does_not_redirect(self):
        image = SimpleUploadedFile("popup.png", b"fake-image-content", content_type="image/png")

        response = self.client.post(reverse("import") + "?popup=1", {"image": image})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gallery/import_popup.html")
        self.assertTemplateNotUsed(response, "layout.html")
        self.assertContains(response, "Votre image a été ajoutée")

    def test_import_popup_post_invalid_shows_error(self):
        response = self.client.post(reverse("import") + "?popup=1", {})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gallery/import_popup.html")
        self.assertContains(response, "Veuillez corriger les erreurs")

    def test_import_into_folder_from_query_string(self):
        folder = self.user_dir / "Mes images"
        folder.mkdir(parents=True)
        image = SimpleUploadedFile("photo.png", b"fake-image-content", content_type="image/png")

        response = self.client.post(reverse("import") + "?folder=Mes images", {"image": image})

        self.assertEqual(response.status_code, 302)
        files = [path for path in folder.iterdir() if path.is_file() and path.name != "index.html"]
        self.assertEqual(len(files), 1)

    def test_import_uses_uuid_instead_of_original_name(self):
        image = SimpleUploadedFile("vacances.png", b"fake-image-content", content_type="image/png")

        response = self.client.post(reverse("import"), {"image": image})

        self.assertRedirects(response, reverse("home_gallery"))
        files = [path for path in self.user_dir.iterdir() if path.is_file() and path.name != "index.html"]
        self.assertEqual(len(files), 1)
        self.assertNotEqual(files[0].name, "vacances.png")
        self.assertRegex(files[0].stem, rf"^[0-9a-f]{{{len(uuid.uuid4().hex)}}}$")
        self.assertEqual(files[0].suffix, ".png")

    def test_import_into_folder(self):
        folder = self.user_dir / "Mes images"
        folder.mkdir(parents=True)
        image = SimpleUploadedFile("photo.jpg", b"fake-image-content", content_type="image/jpeg")

        response = self.client.post(reverse("import"), {"image": image, "folder": "Mes images"})

        self.assertEqual(response.status_code, 302)
        files = [path for path in folder.iterdir() if path.is_file() and path.name != "index.html"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].suffix, ".jpg")

    def test_create_folder(self):
        response = self.client.post(reverse("gallery_create_folder"), {"name": "Mes images"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue((self.user_dir / "Mes images").is_dir())

    def test_create_folder_rejects_path_traversal(self):
        response = self.client.post(reverse("gallery_create_folder"), {"name": "../evil"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse((Path(self.media_root) / "galleries" / "evil").exists())
        self.assertFalse((self.user_dir.parent / "evil").exists())

    def test_move_image_to_folder(self):
        self.user_dir.mkdir(parents=True)
        image_path = self.user_dir / "ancienne.jpg"
        image_path.write_bytes(b"fake-image-content")
        folder = self.user_dir / "Dossier"
        folder.mkdir()

        response = self.client.post(
            reverse("gallery_move_image"),
            {"image": "ancienne.jpg", "folder": "", "target": "Dossier"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(image_path.exists())
        self.assertTrue((folder / "ancienne.jpg").is_file())

    def test_delete_image(self):
        self.user_dir.mkdir(parents=True)
        image_path = self.user_dir / "asupprimer.jpg"
        image_path.write_bytes(b"fake-image-content")

        response = self.client.post(
            reverse("gallery_delete_image"),
            {"image": "asupprimer.jpg", "folder": ""},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(image_path.exists())

    def test_old_images_are_kept_with_their_original_name(self):
        self.user_dir.mkdir(parents=True)
        legacy_image = self.user_dir / "ancienne-image.jpg"
        legacy_image.write_bytes(b"fake-image-content")

        response = self.client.get(reverse("home_gallery"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(legacy_image.is_file())
        self.assertContains(response, "ancienne-image.jpg")

    def test_gallery_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("home_gallery"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login", response.url)
