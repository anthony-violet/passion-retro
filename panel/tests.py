from django.test import TestCase
from django.urls import reverse
from posts.models import NavSection, Category
from users.models import User


class NavSectionPanelTest(TestCase):
    def setUp(self):
        NavSection.objects.all().delete()
        self.category = Category.objects.create(name='Test Category')
        self.staff = User.objects.create_user(
            username='staffuser',
            email='staff@test.com',
            password='testpass123',
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username='regularuser',
            email='regular@test.com',
            password='testpass123',
        )

    def test_non_staff_redirected(self):
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('panel_nav_sections'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_list(self):
        self.client.login(username='staffuser', password='testpass123')
        response = self.client.get(reverse('panel_nav_sections'))
        self.assertEqual(response.status_code, 200)

    def test_create_section(self):
        self.client.login(username='staffuser', password='testpass123')
        response = self.client.post(reverse('panel_nav_section_create'), {
            'label': 'Jeux',
            'category': self.category.id,
            'order': 1,
            'visible': 'on',
            'icon': '🎮',
        })
        self.assertEqual(response.status_code, 302)
        section = NavSection.objects.get(label='Jeux')
        self.assertEqual(section.category, self.category)
        self.assertTrue(section.visible)
        self.assertEqual(section.icon, '🎮')

    def test_edit_section(self):
        section = NavSection.objects.create(
            label='Jeux', category=self.category, order=1
        )
        self.client.login(username='staffuser', password='testpass123')
        self.client.post(reverse('panel_nav_section_edit', args=[section.id]), {
            'label': 'Jeux vidéo',
            'category': self.category.id,
            'order': 5,
        })
        section.refresh_from_db()
        self.assertEqual(section.label, 'Jeux vidéo')
        self.assertEqual(section.order, 5)
        self.assertFalse(section.visible)

    def test_toggle_visibility(self):
        section = NavSection.objects.create(
            label='Jeux', category=self.category, visible=True
        )
        self.client.login(username='staffuser', password='testpass123')
        self.client.post(reverse('panel_nav_section_toggle', args=[section.id]))
        section.refresh_from_db()
        self.assertFalse(section.visible)

    def test_delete_section(self):
        section = NavSection.objects.create(label='Jeux', category=self.category)
        self.client.login(username='staffuser', password='testpass123')
        self.client.post(reverse('panel_nav_section_delete', args=[section.id]))
        self.assertFalse(NavSection.objects.filter(id=section.id).exists())
