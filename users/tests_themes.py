from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Item
from users.forms import UserUpdateForm
from users.models import User
from users.themes import PAID_THEMES, theme_options


class PaidThemesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='membre', password='pass', gold=500,
                                             starting_gold_given=True)
        category = Category.objects.create(name='Thèmes', description='')
        self.rpg = Item.objects.create(category=category, name='Thème RPG', kind=Item.KIND_THEME,
                                       css_class='rpg', price=150)
        self.client.force_login(self.user)

    def set_theme(self, code):
        self.client.post(reverse('set_theme'), {'theme': code, 'next': '/'})
        self.user.refresh_from_db()
        return self.user.theme

    def test_only_three_paid_themes(self):
        self.assertEqual(PAID_THEMES, {'rpg', 'modern', '80s'})

    def test_free_themes_can_be_chosen(self):
        for code in ('retrorpg', '00s', 'vhs', 'default'):
            self.assertEqual(self.set_theme(code), code)

    def test_paid_theme_locked_until_bought(self):
        self.assertEqual(self.set_theme('rpg'), 'default')
        self.assertEqual(self.set_theme('modern'), 'default')
        self.client.post(reverse('shop_buy', args=[self.rpg.pk]))
        self.assertEqual(self.set_theme('rpg'), 'rpg')

    def test_unknown_theme_and_get_are_refused(self):
        self.assertEqual(self.set_theme('../evil'), 'default')
        self.assertEqual(self.client.get(reverse('set_theme_named', args=['vhs'])).status_code, 405)

    def test_external_next_is_ignored(self):
        response = self.client.post(reverse('set_theme'), {'theme': 'vhs', 'next': 'https://evil.example/'})
        self.assertEqual(response['Location'], '/')

    def test_menu_marks_locked_themes(self):
        locked = {code for code, _, is_locked in theme_options(self.user) if is_locked}
        self.assertEqual(locked, {'rpg', 'modern', '80s'})
        self.user.inventory.create(item=self.rpg)
        locked = {code for code, _, is_locked in theme_options(self.user) if is_locked}
        self.assertEqual(locked, {'modern', '80s'})

    def test_profile_form_offers_only_unlocked_themes(self):
        codes = dict(UserUpdateForm(instance=self.user).fields['theme'].choices)
        self.assertIn('vhs', codes)
        self.assertNotIn('rpg', codes)
        self.user.inventory.create(item=self.rpg)
        codes = dict(UserUpdateForm(instance=self.user).fields['theme'].choices)
        self.assertIn('rpg', codes)
