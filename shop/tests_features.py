"""Achats en boutique et utilisation des objets de l'inventaire."""

from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Item
from users.models import User, UserInventory


class ShopPurchaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        currency = Category.objects.create(name='Monnaie', description='')
        cls.frames = Category.objects.create(name='cadres', description='')
        cls.gold = Item.objects.create(category=currency, name='Or', description='', price=0)
        cls.frame = Item.objects.create(category=cls.frames, name='Cadre Doré', description='', price=50)
        cls.hidden = Item.objects.create(
            category=cls.frames, name='Cadre Retiré', description='', price=1, is_active=False
        )

    def setUp(self):
        self.user = User.objects.create_user(username='client', password='pass')
        UserInventory.objects.create(user=self.user, item=self.gold, quantity=100)
        self.client.force_login(self.user)

    def buy(self, item):
        return self.client.get(reverse('shop_buy', args=[item.id]))

    def test_buy_item_debits_gold(self):
        response = self.buy(self.frame)
        self.assertRedirects(response, reverse('shop_home'))
        self.assertEqual(self.user.money, 50)
        self.assertTrue(self.user.inventory.filter(item=self.frame).exists())

    def test_cannot_buy_twice(self):
        self.buy(self.frame)
        self.buy(self.frame)
        self.assertEqual(self.user.money, 50)
        self.assertEqual(self.user.inventory.filter(item=self.frame).count(), 1)

    def test_cannot_buy_without_enough_gold(self):
        UserInventory.objects.filter(user=self.user, item=self.gold).update(quantity=10)
        self.buy(self.frame)
        self.assertEqual(self.user.money, 10)
        self.assertFalse(self.user.inventory.filter(item=self.frame).exists())

    def test_cannot_buy_inactive_item(self):
        self.assertEqual(self.buy(self.hidden).status_code, 404)
        self.assertFalse(self.user.inventory.filter(item=self.hidden).exists())

    def test_unknown_item_returns_404(self):
        self.assertEqual(self.client.get(reverse('shop_buy', args=[999999])).status_code, 404)

    def test_buy_requires_login(self):
        self.client.logout()
        self.assertEqual(self.buy(self.frame).status_code, 302)

    def test_use_owned_frame(self):
        self.buy(self.frame)
        response = self.client.get(reverse('use_item', args=[self.frame.id]))
        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.border_avatar, 'cadre-dore')

    def test_use_item_not_owned(self):
        response = self.client.get(reverse('use_item', args=[self.frame.id]))
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.border_avatar, 'cadre-dore')
