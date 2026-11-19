from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from shop.models import Category, Item
from users.models import User


class ItemModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Cadres', description='')
        self.item = Item.objects.create(category=self.category, name='Cadre Doré', price=100,
                                        kind=Item.KIND_FRAME)

    def test_str(self):
        self.assertEqual(str(self.item), 'Cadre Doré')
        self.assertEqual(str(self.category), 'Cadres')

    def test_slug_defaults_to_name_and_can_be_overridden(self):
        self.assertEqual(self.item.slug, 'cadre-dore')
        self.item.css_class = 'gold-frame'
        self.assertEqual(self.item.slug, 'gold-frame')

    def test_discount_only_during_its_period(self):
        now = timezone.now()
        self.item.discount_percent = 25
        self.assertEqual(self.item.current_price(now), 75)
        self.item.discount_until = now - timedelta(minutes=1)
        self.assertEqual(self.item.current_price(now), 100)
        self.item.discount_until = None
        self.item.discount_from = now + timedelta(days=1)
        self.assertEqual(self.item.current_price(now), 100)

    def test_availability_window_and_stock(self):
        now = timezone.now()
        self.assertTrue(self.item.is_available(now))
        self.item.available_from = now + timedelta(days=1)
        self.assertFalse(self.item.is_available(now))
        self.item.available_from = None
        self.item.available_until = now - timedelta(seconds=1)
        self.assertFalse(self.item.is_available(now))
        self.item.available_until = None
        self.item.stock = 0
        self.assertTrue(self.item.is_on_sale(now))
        self.assertFalse(self.item.is_available(now))

    def test_on_sale_queryset(self):
        now = timezone.now()
        Item.objects.create(category=self.category, name='Futur', available_from=now + timedelta(days=2))
        Item.objects.create(category=self.category, name='Fini', available_until=now - timedelta(days=2))
        Item.objects.create(category=self.category, name='Inactif', is_active=False)
        self.assertEqual([i.name for i in Item.objects.on_sale(now)], ['Cadre Doré'])

    def test_only_consumables_stack(self):
        self.assertFalse(self.item.is_stackable)
        self.item.kind = Item.KIND_CONSUMABLE
        self.assertTrue(self.item.is_stackable)


class ShopPageTest(TestCase):
    def setUp(self):
        self.frames = Category.objects.create(name='Cadres', description='')
        self.potions = Category.objects.create(name='Potions', description='')
        self.frame = Item.objects.create(category=self.frames, name='Cadre Doré', price=50,
                                         kind=Item.KIND_FRAME, rarity=Item.RARITY_EPIC)
        self.potion = Item.objects.create(category=self.potions, name="Potion d'XP", price=30,
                                          kind=Item.KIND_CONSUMABLE, effect=Item.EFFECT_XP_BOOST,
                                          discount_percent=50)
        self.user = User.objects.create_user(username='acheteur', password='testpass123',
                                             gold=100, starting_gold_given=True)

    def test_anonymous_visitors_see_catalogue_without_buy_buttons(self):
        response = self.client.get(reverse('shop_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cadre Doré')
        self.assertContains(response, 'Connecte-toi pour acheter')
        self.assertNotContains(response, 'class="sh-buy"')

    def test_members_see_balance_and_buy_buttons(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('shop_home'))
        self.assertContains(response, 'Mon or')
        self.assertContains(response, 'class="sh-buy"')
        self.assertContains(response, 'Épique')
        self.assertContains(response, '<del>30</del>', html=False)

    def test_category_and_promo_filters(self):
        response = self.client.get(reverse('shop_home'), {'categorie': self.frames.pk})
        self.assertContains(response, 'Cadre Doré')
        self.assertNotContains(response, "Potion d&#x27;XP")
        response = self.client.get(reverse('shop_home'), {'filtre': 'promos'})
        self.assertNotContains(response, 'Cadre Doré')
        self.assertContains(response, "Potion d&#x27;XP")

    def test_bad_query_params_are_ignored(self):
        response = self.client.get(reverse('shop_home'), {'categorie': 'abc', 'tri': 'nimporte'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cadre Doré')

    def test_owned_unique_item_shows_possede_without_buy_button(self):
        self.user.inventory.create(item=self.frame)
        self.client.force_login(self.user)
        response = self.client.get(reverse('shop_home'), {'categorie': self.frames.pk})
        self.assertContains(response, 'Possédé')
        self.assertNotContains(response, 'class="sh-buy"')

    def test_inventory_page(self):
        self.user.inventory.create(item=self.frame)
        self.user.inventory.create(item=self.potion, quantity=3)
        self.client.force_login(self.user)
        response = self.client.get(reverse('shop_inventory'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cadre Doré')
        self.assertContains(response, 'x3')
        self.assertContains(response, 'Équiper')
        self.assertContains(response, 'Utiliser')

    def test_inventory_requires_login(self):
        self.assertEqual(self.client.get(reverse('shop_inventory')).status_code, 302)
