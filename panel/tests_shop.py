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


class ThemeStatsTest(TestCase):
    def test_theme_usage_counts(self):
        from datetime import timedelta

        from django.utils import timezone

        from panel.views.stats import theme_usage

        category = Category.objects.create(name='Thèmes', description='')
        rpg = Item.objects.create(category=category, name='Thème RPG X', kind='theme', css_class='rpg')
        now = timezone.now()
        a = User.objects.create_user('a', theme='rpg', last_seen=now)
        User.objects.create_user('b', theme='rpg', last_seen=now - timedelta(days=60))
        User.objects.create_user('c', theme='retrogame')
        User.objects.create_user('d', theme='vhs', is_active=False)
        a.inventory.create(item=rpg)

        rows, total = theme_usage(now - timedelta(days=30))
        by_code = {row['code']: row for row in rows}
        self.assertEqual(total, 3)
        self.assertEqual((by_code['rpg']['count'], by_code['rpg']['active'], by_code['rpg']['share']), (2, 1, 67))
        self.assertGreaterEqual(by_code['rpg']['owners'], 1)
        self.assertFalse(by_code['retrogame']['known'])
        self.assertEqual(by_code['vhs']['count'], 0)
        self.assertIsNone(by_code['vhs']['owners'])
        self.assertEqual(rows[0]['code'], 'rpg')

    def test_stats_page_shows_themes(self):
        staff = User.objects.create_user('staff', 's@test.com', 'pass12345', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse('panel_stats'))
        self.assertContains(response, 'Thèmes des membres')
        self.assertContains(response, 'RetroRPG')
