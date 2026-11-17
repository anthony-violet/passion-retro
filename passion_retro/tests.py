from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from passion_retro.context_processors import analytics_context


class AnalyticsContextTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, path="/", is_authenticated=False):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=is_authenticated)
        return request

    @override_settings(GTM_CONTAINER_ID="", DEBUG=False)
    def test_disabled_without_container_id(self):
        context = analytics_context(self._request())
        self.assertFalse(context["analytics_tracking"])
        self.assertEqual(context["gtm_container_id"], "")

    @override_settings(GTM_CONTAINER_ID="GTM-TEST", DEBUG=False)
    def test_enabled_on_public_page_for_anonymous_user(self):
        context = analytics_context(self._request("/"))
        self.assertTrue(context["analytics_tracking"])
        self.assertEqual(context["gtm_container_id"], "GTM-TEST")

    @override_settings(GTM_CONTAINER_ID="GTM-TEST", DEBUG=True)
    def test_disabled_in_debug(self):
        self.assertFalse(analytics_context(self._request("/"))["analytics_tracking"])

    @override_settings(GTM_CONTAINER_ID="GTM-TEST", DEBUG=False)
    def test_disabled_for_authenticated_user(self):
        request = self._request("/", is_authenticated=True)
        self.assertFalse(analytics_context(request)["analytics_tracking"])

    @override_settings(GTM_CONTAINER_ID="GTM-TEST", DEBUG=False)
    def test_disabled_on_private_pages(self):
        paths = (
            "/admin/",
            "/panel/",
            "/pm/",
            "/users/activate/abc/def/",
            "/users/profile/",
            "/users/contributions/",
            "/users/item/1/",
            "/users/new/feature",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(analytics_context(self._request(path))["analytics_tracking"])

    @override_settings(GTM_CONTAINER_ID="GTM-TEST", DEBUG=False)
    def test_enabled_on_public_content_pages(self):
        paths = (
            "/",
            "/posts/",
            "/forum/",
            "/gallery/",
            "/quiz/",
            "/shop/",
            "/ephemerides/",
            "/games/",
            "/version/history",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(analytics_context(self._request(path))["analytics_tracking"])


class ChristmasDecorTest(TestCase):
    """Décor de Noël : réglé dans le panel (par défaut 1er décembre → 10 janvier), masquable par cookie."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def _set(self, **fields):
        from home.models import ChristmasSettings
        obj, _ = ChristmasSettings.objects.get_or_create(pk=1)
        for name, value in fields.items():
            setattr(obj, name, value)
        obj.save()

    def _get_home(self, day=None, **cookies):
        from datetime import date
        from unittest import mock
        for name, value in cookies.items():
            self.client.cookies[name] = value
        with mock.patch('passion_retro.christmas.timezone.localdate', return_value=day or date(2026, 12, 15)):
            return self.client.get(reverse('home'))

    def test_default_period_crosses_new_year(self):
        from datetime import date
        from home.models import ChristmasSettings
        obj = ChristmasSettings()  # valeurs par défaut : 1/12 → 10/01
        self.assertFalse(obj.includes(date(2026, 11, 30)))
        self.assertTrue(obj.includes(date(2026, 12, 1)))
        self.assertTrue(obj.includes(date(2026, 12, 25)))
        self.assertTrue(obj.includes(date(2027, 1, 10)))
        self.assertFalse(obj.includes(date(2027, 1, 11)))
        self.assertFalse(obj.includes(date(2027, 7, 14)))

    def test_period_within_same_year(self):
        from datetime import date
        from home.models import ChristmasSettings
        obj = ChristmasSettings(start_day=15, start_month=12, end_day=31, end_month=12)
        self.assertFalse(obj.includes(date(2026, 12, 14)))
        self.assertTrue(obj.includes(date(2026, 12, 15)))
        self.assertTrue(obj.includes(date(2026, 12, 31)))
        self.assertFalse(obj.includes(date(2027, 1, 1)))

    def test_invalid_date_rejected(self):
        from django.core.exceptions import ValidationError
        from home.models import ChristmasSettings
        with self.assertRaises(ValidationError):
            ChristmasSettings(start_day=31, start_month=2).full_clean()
        ChristmasSettings(start_day=29, start_month=2).full_clean()  # 29 février accepté

    def test_decor_shown_during_period(self):
        response = self._get_home()
        self.assertContains(response, 'christmas/christmas.js')
        self.assertContains(response, 'xmas-trees')
        self.assertContains(response, ' xmas"')
        self.assertContains(response, 'Décor de Noël : activé')

    def test_nothing_outside_period(self):
        from datetime import date
        response = self._get_home(date(2026, 11, 17))
        self.assertNotContains(response, 'christmas/christmas.js')
        self.assertNotContains(response, 'xmas-trees')
        self.assertNotContains(response, 'Décor de Noël')

    def test_cookie_disables_decor_but_keeps_toggle(self):
        from passion_retro.christmas import COOKIE_NAME
        response = self._get_home(**{COOKIE_NAME: '1'})
        self.assertNotContains(response, 'christmas/christmas.js')
        self.assertNotContains(response, 'xmas-trees')
        self.assertContains(response, 'Décor de Noël : désactivé')

    def test_toggle_view_switches_cookie(self):
        from passion_retro.christmas import COOKIE_NAME
        url = reverse('toggle_christmas')
        response = self.client.post(url, {'next': '/forum/'})
        self.assertRedirects(response, '/forum/', fetch_redirect_response=False)
        self.assertEqual(response.cookies[COOKIE_NAME].value, '1')

        self.client.cookies[COOKIE_NAME] = '1'
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'enabled': True})
        self.assertEqual(response.cookies[COOKIE_NAME].value, '')  # cookie supprimé

    def test_toggle_view_refuses_get_and_external_redirect(self):
        url = reverse('toggle_christmas')
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {'next': 'https://exemple.com/'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_edited_dates_apply_to_site(self):
        from datetime import date
        self._set(start_day=15, start_month=11, end_day=20, end_month=11)
        self.assertContains(self._get_home(date(2026, 11, 17)), 'christmas/christmas.js')
        self.assertNotContains(self._get_home(date(2026, 12, 15)), 'christmas/christmas.js')

    def test_mode_forces_on_or_off(self):
        from datetime import date
        self._set(mode='on')
        self.assertContains(self._get_home(date(2026, 7, 1)), 'christmas/christmas.js')
        self._set(mode='off')
        self.assertNotContains(self._get_home(date(2026, 12, 24)), 'christmas/christmas.js')

    def test_panel_page_is_staff_only(self):
        from users.models import User
        url = reverse('panel_christmas')
        self.assertRedirects(self.client.get(url), reverse('home'), fetch_redirect_response=False)
        member = User.objects.create_user(username='membre', email='m@test.com', password='pass12345', active=True)
        self.client.force_login(member)
        self.assertRedirects(self.client.get(url), reverse('home'), fetch_redirect_response=False)

    def test_panel_saves_settings(self):
        from home.models import ChristmasSettings
        from users.models import User
        staff = User.objects.create_user(username='modo', email='modo@test.com', password='pass12345', active=True, is_staff=True)
        self.client.force_login(staff)
        url = reverse('panel_christmas')
        self.assertContains(self.client.get(url), 'Décor de Noël')
        response = self.client.post(url, {
            'mode': 'auto', 'start_day': 5, 'start_month': 12, 'end_day': 6, 'end_month': 1,
        })
        self.assertRedirects(response, url, fetch_redirect_response=False)
        obj = ChristmasSettings.objects.get(pk=1)
        self.assertEqual((obj.start_day, obj.start_month, obj.end_day, obj.end_month), (5, 12, 6, 1))

    def test_panel_rejects_invalid_date(self):
        from home.models import ChristmasSettings
        from users.models import User
        staff = User.objects.create_user(username='modo2', email='modo2@test.com', password='pass12345', active=True, is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse('panel_christmas'), {
            'mode': 'auto', 'start_day': 31, 'start_month': 2, 'end_day': 10, 'end_month': 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "n&#x27;existe pas")
        self.assertFalse(ChristmasSettings.objects.filter(start_month=2).exists())
