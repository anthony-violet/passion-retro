from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from messagerie.models import PrivateMessageSubject
from shop.models import Category, Item
from users.models import StaffReward, User, UserInventory


class StaffRewardPanelTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', 'staff@test.com', 'pass12345', is_staff=True)
        self.alice = User.objects.create_user('Alice', 'a@test.com', 'pass12345')
        self.bob = User.objects.create_user('bob', 'b@test.com', 'pass12345')
        self.bot = User.objects.create_user('RetroBot', 'r@test.com', 'pass12345')
        category = Category.objects.create(name='Cat', description='d',
                                           image=SimpleUploadedFile('c.gif', b'GIF89a'))
        self.gold = Item.objects.create(category=category, name='Or', description='d', price=0,
                                        image=SimpleUploadedFile('o.gif', b'GIF89a'))
        self.trophy = Item.objects.create(category=category, name='Trophée', description='d', price=50,
                                          image=SimpleUploadedFile('t.gif', b'GIF89a'))
        self.url = reverse('panel_rewards')

    def post(self, **data):
        self.client.login(username='staff', password='pass12345')
        payload = {'usernames': 'Alice', 'reason': 'Concours de Noël', 'notify': 'on'}
        payload.update(data)
        return self.client.post(self.url, payload)

    def test_non_staff_redirected(self):
        self.client.login(username='bob', password='pass12345')
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(self.url, {'usernames': 'bob', 'reason': 'x', 'gold': '999'})
        self.assertFalse(StaffReward.objects.exists())

    def test_staff_page_loads(self):
        self.client.login(username='staff', password='pass12345')
        response = self.client.get(self.url + '?user=Alice')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trophée')
        self.assertNotContains(response, '<option value="%d"' % self.gold.pk)

    def test_give_xp_gold_and_item_to_several_members(self):
        response = self.post(usernames='alice, BOB', experience='40', gold='25', item=self.trophy.pk)
        self.assertRedirects(response, self.url)
        for user in (self.alice, self.bob):
            self.assertGreaterEqual(user.experience, 40)
            self.assertTrue(UserInventory.objects.filter(user=user, item=self.trophy).exists())
            # Or de départ (100) + 25 + bonus de passage de niveau éventuel
            self.assertGreaterEqual(user.money, 125)
            self.assertTrue(PrivateMessageSubject.objects.filter(
                receiver=user, subject__contains='Concours de Noël').exists())
        reward = StaffReward.objects.get(user=self.alice)
        self.assertEqual((reward.experience, reward.gold, reward.item, reward.given_by),
                         (40, 25, self.trophy, self.staff))

    def test_gold_added_to_existing_balance(self):
        UserInventory.objects.create(user=self.alice, item=self.gold, quantity=10)
        self.post(gold='5')
        self.assertEqual(self.alice.money, 15)

    def test_item_already_owned_is_not_given_twice(self):
        UserInventory.objects.create(user=self.alice, item=self.trophy)
        self.post(item=self.trophy.pk)
        self.assertEqual(UserInventory.objects.filter(user=self.alice, item=self.trophy).count(), 1)
        self.assertFalse(StaffReward.objects.exists())

    def test_without_notification(self):
        self.post(gold='5', notify='')
        self.assertEqual(StaffReward.objects.count(), 1)
        self.assertFalse(PrivateMessageSubject.objects.filter(subject__contains='récompense').exists())

    def test_unknown_member_gives_nothing(self):
        response = self.post(usernames='Alice inconnu', gold='5', follow=True)
        self.assertContains(response, 'introuvable')
        self.assertFalse(StaffReward.objects.exists())

    def test_requires_reason_and_reward(self):
        self.post(reason='', gold='5')
        self.post(gold='', experience='')
        self.post(gold='-3')
        self.assertFalse(StaffReward.objects.exists())

    def test_member_search(self):
        User.objects.create_user('malice', 'm@test.com', 'pass12345')
        url = reverse('panel_rewards_members')
        self.client.login(username='staff', password='pass12345')
        names = [r['username'] for r in self.client.get(url, {'q': 'ali'}).json()['results']]
        # Les pseudos qui commencent par la recherche passent en premier.
        self.assertEqual(names, ['Alice', 'malice'])
        self.assertEqual(self.client.get(url, {'q': 'retro'}).json()['results'], [])
        self.assertEqual(self.client.get(url).json()['results'], [])

    def test_member_search_staff_only(self):
        self.client.login(username='bob', password='pass12345')
        response = self.client.get(reverse('panel_rewards_members'), {'q': 'a'})
        self.assertEqual(response.status_code, 302)
