from django.test import TestCase
from shop.models import Item, Category
from users.models import User

class ShopModelsTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Test Category',
            description='Description de test',
            is_active=True
        )
        
        self.item = Item.objects.create(
            category=self.category,
            name='Test Item',
            description='Description de l\'article',
            price=10.99,
            is_active=True
        )
    
    def test_create_category(self):
        self.assertEqual(self.category.name, 'Test Category')
        self.assertTrue(self.category.is_active)
    
    def test_create_item(self):
        self.assertEqual(self.item.name, 'Test Item')
        self.assertEqual(self.item.price, 10.99)
        self.assertEqual(self.item.category, self.category)
        self.assertTrue(self.item.is_active)
    
    def test_item_string_representation(self):
        self.assertEqual(str(self.item), 'Test Item')
    
    def test_category_string_representation(self):
        self.assertEqual(str(self.category), 'Test Category')

class ShopBasicTest(TestCase):
    def test_shop_app_exists(self):
        # Test basique pour vérifier que l'application shop est installée
        from django.apps import apps
        self.assertTrue(apps.is_installed('shop'))
    
    def test_shop_models_exist(self):
        # Vérifier que les modèles principaux existent
        self.assertTrue(hasattr(Item, 'objects'))
        self.assertTrue(hasattr(Category, 'objects'))
