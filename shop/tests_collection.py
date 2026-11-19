"""Objets de collection : objet fétiche, vitrine du profil et balise BBCode [objet]."""
from django.test import TestCase
from django.urls import reverse

from commons.bbcode_parser import BBCodeParser
from shop.models import Category, Item
from shop.services import ShopError, toggle_featured, toggle_showcase
from shop.templatetags.shop_tags import featured_collectible
from users.models import User, UserInventory


class CollectionTest(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Collection test')
        self.items = [
            Item.objects.create(category=category, name=f'Relique <{n}>', kind=Item.KIND_COLLECTIBLE,
                                css_class=f'relique-{n}', rarity=Item.RARITY_EPIC)
            for n in range(4)
        ]
        self.frame = Item.objects.create(category=category, name='Cadre', kind=Item.KIND_FRAME)
        self.user = User.objects.create_user(username='collec', password='testpass123')
        self.other = User.objects.create_user(username='autre', password='testpass123')
        self.entries = [UserInventory.objects.create(user=self.user, item=item) for item in self.items]
        UserInventory.objects.create(user=self.user, item=self.frame)

    # --- Objet fétiche -----------------------------------------------------
    def test_toggle_featured(self):
        toggle_featured(self.user, self.items[0].pk)
        self.user.refresh_from_db()
        self.assertEqual(self.user.featured_collectible, self.items[0])
        badge = featured_collectible(self.user)
        self.assertIn('featured-collectible--epic', badge)
        self.assertIn('Relique &lt;0&gt;', badge)

        toggle_featured(self.user, self.items[0].pk)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.featured_collectible)
        self.assertEqual(featured_collectible(self.user), '')

    def test_only_owned_collectibles_can_be_featured(self):
        with self.assertRaises(ShopError):
            toggle_featured(self.other, self.items[0].pk)
        with self.assertRaises(ShopError):
            toggle_featured(self.user, self.frame.pk)

    def test_losing_the_item_removes_it_everywhere(self):
        toggle_featured(self.user, self.items[0].pk)
        toggle_showcase(self.user, self.items[1].pk)
        self.entries[0].delete()
        self.entries[1].quantity = 0
        self.entries[1].save()
        self.user.refresh_from_db()
        self.assertIsNone(self.user.featured_collectible)
        self.assertFalse(UserInventory.objects.get(pk=self.entries[1].pk).showcased)

    # --- Vitrine -----------------------------------------------------------
    def test_showcase_is_limited_to_three(self):
        for item in self.items[:3]:
            toggle_showcase(self.user, item.pk)
        with self.assertRaises(ShopError):
            toggle_showcase(self.user, self.items[3].pk)
        toggle_showcase(self.user, self.items[0].pk)
        toggle_showcase(self.user, self.items[3].pk)
        self.assertEqual(UserInventory.objects.filter(user=self.user, showcased=True).count(), 3)

    def test_public_profile_shows_showcase(self):
        toggle_showcase(self.user, self.items[2].pk)
        response = self.client.get(reverse('profile', args=[self.user.pk]))
        self.assertContains(response, 'Sa vitrine')
        self.assertContains(response, 'Relique &lt;2&gt;')
        response = self.client.get(reverse('profile', args=[self.other.pk]))
        self.assertNotContains(response, 'Sa vitrine')

    def test_inventory_actions(self):
        self.client.force_login(self.user)
        url = reverse('shop_collectible_action', args=[self.items[0].pk])
        self.client.post(url, {'action': 'featured'})
        self.client.post(url, {'action': 'showcase'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.featured_collectible, self.items[0])
        self.assertTrue(UserInventory.objects.get(pk=self.entries[0].pk).showcased)
        response = self.client.get(reverse('shop_inventory'))
        self.assertContains(response, 'Fétiche · retirer')

    # --- BBCode ------------------------------------------------------------
    def test_bbcode_renders_owned_item_with_owner(self):
        html = BBCodeParser().parse(f'Voici [objet]{self.entries[1].pk}[/objet] !', allow_html=False)
        self.assertIn('collectible-card--epic', html)
        self.assertIn('Relique &lt;1&gt;', html)
        self.assertIn('Collection de collec', html)
        self.assertNotIn('[objet]', html)

    def test_bbcode_hides_items_no_longer_owned_or_not_collectible(self):
        frame_entry = UserInventory.objects.get(item=self.frame)
        gone_pk = self.entries[0].pk
        self.entries[0].delete()
        html = BBCodeParser().parse(f'[objet]{gone_pk}[/objet] [objet]{frame_entry.pk}[/objet]')
        self.assertEqual(html.count('Objet de collection indisponible'), 2)

    def test_my_collection_json(self):
        self.assertTrue(self.client.get(reverse('shop_my_collection')).json()['login_required'])
        self.client.force_login(self.user)
        data = self.client.get(reverse('shop_my_collection')).json()
        self.assertEqual(len(data['items']), 4)
        self.assertEqual({row['id'] for row in data['items']}, {entry.pk for entry in self.entries})
