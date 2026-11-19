from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Item
from users.models import User


class PanelShopTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', 'staff@test.com', 'pass12345', is_staff=True)
        self.category = Category.objects.create(name='Potions', description='')
        self.client.force_login(self.staff)

    def test_pages_load(self):
        item = Item.objects.create(category=self.category, name='Potion', price=10, discount_percent=20, stock=3)
        self.assertContains(self.client.get(reverse('panel_shop')), '<del>10</del> 8', html=False)
        self.assertEqual(self.client.get(reverse('panel_shop_item_create')).status_code, 200)
        self.assertContains(self.client.get(reverse('panel_shop_item_edit', args=[item.pk])), 'name="discount_percent"')
        self.assertEqual(self.client.get(reverse('panel_shop_category_edit', args=[self.category.pk])).status_code, 200)

    def test_create_item_with_new_mechanics(self):
        self.client.post(reverse('panel_shop_item_create'), {
            'name': "Potion d'XP", 'category': self.category.pk, 'kind': 'consumable', 'rarity': 'epic',
            'price': '80', 'discount_percent': '150', 'stock': '5', 'effect': 'xp_boost', 'effect_hours': '12',
            'available_until': '2030-01-01T12:00', 'is_active': 'on',
        })
        item = Item.objects.get(name="Potion d'XP")
        self.assertEqual((item.kind, item.rarity, item.price, item.stock, item.effect, item.effect_hours),
                         ('consumable', 'epic', 80, 5, 'xp_boost', 12))
        self.assertEqual(item.discount_percent, 90)  # plafonné
        self.assertEqual(item.available_until.year, 2030)

    def test_empty_stock_means_unlimited_and_category_position(self):
        item = Item.objects.create(category=self.category, name='Cadre', price=10, stock=2)
        self.client.post(reverse('panel_shop_item_edit', args=[item.pk]), {
            'name': 'Cadre', 'category': self.category.pk, 'kind': 'frame', 'price': '10', 'stock': '',
        })
        item.refresh_from_db()
        self.assertIsNone(item.stock)
        self.client.post(reverse('panel_shop_category_edit', args=[self.category.pk]),
                         {'name': 'Potions', 'position': '3', 'is_active': 'on'})
        self.category.refresh_from_db()
        self.assertEqual(self.category.position, 3)
