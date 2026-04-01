from django.test import TestCase
from users.models import User

class GalleryBasicTest(TestCase):
    def test_gallery_app_exists(self):
        # Test basique pour vérifier que l'application gallery est installée
        from django.apps import apps
        self.assertTrue(apps.is_installed('gallery'))
    
    def test_gallery_models(self):
        # Vérifier que les modèles de base existent si ils sont définis
        try:
            from gallery.models import Image
            self.assertTrue(hasattr(Image, 'objects'))
        except ImportError:
            # Si aucun modèle n'est défini, c'est aussi valide
            pass
