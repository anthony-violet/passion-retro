"""Achats en boutique et utilisation des objets de l'inventaire."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from shop.models import Category, Item
from users.leveling import grant_experience
from users.models import User, UserInventory


class ShopPurchaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.frames = Category.objects.create(name='cadres', description='')
        cls.themes = Category.objects.create(name='Thèmes', description='')
        cls.potions = Category.objects.create(name='Potions', description='')
        cls.frame = Item.objects.create(category=cls.frames, name='Cadre Doré', price=50, kind=Item.KIND_FRAME)
        cls.hidden = Item.objects.create(category=cls.frames, name='Cadre Retiré', price=1,
                                         kind=Item.KIND_FRAME, is_active=False)
        cls.theme = Item.objects.create(category=cls.themes, name='Thème RPG', price=10,
                                        kind=Item.KIND_THEME, css_class='rpg')
        cls.potion = Item.objects.create(category=cls.potions, name="Potion d'XP", price=20,
                                         kind=Item.KIND_CONSUMABLE, effect=Item.EFFECT_XP_BOOST, effect_hours=24)
        cls.trophy = Item.objects.create(category=cls.potions, name='Trophée', price=5)

    def setUp(self):
        self.user = User.objects.create_user(username='client', password='pass', gold=100,
                                             starting_gold_given=True)
        self.client.force_login(self.user)

    def buy(self, item):
        return self.client.post(reverse('shop_buy', args=[item.id]))

    def gold(self):
        self.user.refresh_from_db()
        return self.user.gold

    # --- Achat -------------------------------------------------------------
    def test_buy_item_debits_gold(self):
        response = self.buy(self.frame)
        self.assertRedirects(response, reverse('shop_home'), fetch_redirect_response=False)
        self.assertEqual(self.gold(), 50)
        self.assertTrue(self.user.inventory.filter(item=self.frame).exists())

    def test_buy_requires_post(self):
        self.assertEqual(self.client.get(reverse('shop_buy', args=[self.frame.id])).status_code, 405)
        self.assertEqual(self.gold(), 100)

    def test_cannot_buy_unique_item_twice(self):
        self.buy(self.frame)
        self.buy(self.frame)
        self.assertEqual(self.gold(), 50)
        self.assertEqual(self.user.inventory.get(item=self.frame).quantity, 1)

    def test_consumables_stack(self):
        self.buy(self.potion)
        self.buy(self.potion)
        self.assertEqual(self.gold(), 60)
        self.assertEqual(self.user.inventory.get(item=self.potion).quantity, 2)

    def test_cannot_buy_without_enough_gold(self):
        User.objects.filter(pk=self.user.pk).update(gold=10)
        self.buy(self.frame)
        self.assertEqual(self.gold(), 10)
        self.assertFalse(self.user.inventory.filter(item=self.frame).exists())

    def test_cannot_buy_inactive_or_unknown_item(self):
        self.buy(self.hidden)
        self.assertFalse(self.user.inventory.filter(item=self.hidden).exists())
        response = self.client.post(reverse('shop_buy', args=[999999]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.gold(), 100)

    def test_buy_requires_login(self):
        self.client.logout()
        self.assertEqual(self.buy(self.frame).status_code, 302)
        self.assertFalse(UserInventory.objects.filter(item=self.frame).exists())

    def test_discount_is_applied(self):
        Item.objects.filter(pk=self.frame.pk).update(discount_percent=40)
        self.buy(self.frame)
        self.assertEqual(self.gold(), 70)

    def test_stock_decreases_and_sold_out_blocks(self):
        Item.objects.filter(pk=self.potion.pk).update(stock=1)
        self.buy(self.potion)
        self.buy(self.potion)
        self.potion.refresh_from_db()
        self.assertEqual(self.potion.stock, 0)
        self.assertEqual(self.user.inventory.get(item=self.potion).quantity, 1)
        self.assertEqual(self.gold(), 80)

    def test_expired_limited_item_cannot_be_bought(self):
        Item.objects.filter(pk=self.frame.pk).update(available_until=timezone.now() - timedelta(minutes=1))
        self.buy(self.frame)
        self.assertEqual(self.gold(), 100)

    def test_next_redirect_stays_in_shop(self):
        response = self.client.post(reverse('shop_buy', args=[self.trophy.id]), {'next': '/shop/?tri=prix'})
        self.assertEqual(response['Location'], '/shop/?tri=prix')
        response = self.client.post(reverse('shop_buy', args=[self.potion.id]), {'next': 'https://evil.example'})
        self.assertEqual(response['Location'], reverse('shop_home'))

    # --- Utilisation -------------------------------------------------------
    def use(self, item, **data):
        return self.client.post(reverse('use_item', args=[item.id]), data)

    def test_equip_and_unequip_frame(self):
        self.buy(self.frame)
        response = self.use(self.frame)
        self.assertRedirects(response, reverse('shop_inventory'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.border_avatar, 'cadre-dore')
        self.use(self.frame)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.border_avatar)

    def test_equip_theme_sets_member_theme(self):
        self.buy(self.theme)
        self.use(self.theme)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, 'rpg')
        self.use(self.theme)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, 'default')

    def test_use_item_not_owned(self):
        self.use(self.frame)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.border_avatar)

    def test_use_item_requires_post(self):
        self.buy(self.frame)
        self.assertEqual(self.client.get(reverse('use_item', args=[self.frame.id])).status_code, 405)

    def test_use_redirects_to_safe_next_only(self):
        self.buy(self.frame)
        response = self.use(self.frame, next='/shop/inventaire/?type=frame')
        self.assertEqual(response['Location'], '/shop/inventaire/?type=frame')
        response = self.use(self.frame, next='https://evil.example/')
        self.assertEqual(response['Location'], reverse('shop_inventory'))

    def test_collectible_cannot_be_used(self):
        self.buy(self.trophy)
        self.use(self.trophy)
        self.assertEqual(self.user.inventory.get(item=self.trophy).quantity, 1)

    def test_potion_is_consumed_and_doubles_xp(self):
        self.buy(self.potion)
        self.buy(self.potion)
        self.use(self.potion)
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_xp_boost)
        self.assertEqual(self.user.inventory.get(item=self.potion).quantity, 1)

        self.user.levels.create(level=1, experience=0)
        grant_experience(self.user, 5)
        self.assertEqual(self.user.levels.get().experience, 10)
        # Les récompenses du staff ne sont pas doublées.
        grant_experience(self.user, 5, boost=False)
        self.assertEqual(self.user.levels.get().experience, 15)

    def test_second_potion_extends_boost_and_last_one_disappears(self):
        self.buy(self.potion)
        self.buy(self.potion)
        self.use(self.potion)
        self.user.refresh_from_db()
        first_end = self.user.xp_boost_until
        self.use(self.potion)
        self.user.refresh_from_db()
        self.assertAlmostEqual((self.user.xp_boost_until - first_end).total_seconds(), 24 * 3600, delta=5)
        self.assertFalse(self.user.inventory.filter(item=self.potion).exists())

    def test_inventory_marks_equipped_item(self):
        self.buy(self.frame)
        self.use(self.frame)
        response = self.client.get(reverse('shop_inventory'))
        self.assertContains(response, 'Retirer')
        self.assertContains(response, 'sh-status--equipped')


class StartingGoldTest(TestCase):
    def test_onboarding_gives_starting_gold_once(self):
        user = User.objects.create_user(username='nouveau', password='pass')
        user.levels.create(level=1)
        self.client.force_login(user)
        self.client.get(reverse('new_feature_user'))
        self.client.get(reverse('new_feature_user'))
        user.refresh_from_db()
        self.assertEqual(user.gold, 100)
        self.assertTrue(user.starting_gold_given)

    def test_middleware_sends_members_without_starting_gold_to_onboarding(self):
        from django.test import RequestFactory
        from users.middleware import UserLevelMiddleware

        user = User.objects.create_user(username='nouveau', password='pass')
        user.levels.create(level=1)
        request = RequestFactory().get('/shop/')
        request.user = user
        middleware = UserLevelMiddleware(lambda r: None)
        self.assertEqual(middleware.process_request(request).status_code, 302)
        user.starting_gold_given = True
        self.assertIsNone(middleware.process_request(request))
