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


class SeasonalEventsTest(TestCase):
    """Décors thématiques : périodes réglées dans le panel, masquables par cookie."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def _set(self, key, **fields):
        from home.models import SeasonalEvent
        event = SeasonalEvent.objects.get(key=key)
        for name, value in fields.items():
            setattr(event, name, value)
        event.save()

    def _get_home(self, day=None, **cookies):
        from datetime import date
        from unittest import mock
        for name, value in cookies.items():
            self.client.cookies[name] = value
        with mock.patch('passion_retro.seasonal.timezone.localdate', return_value=day or date(2026, 12, 15)):
            return self.client.get(reverse('home'))

    # --- Règles de dates -------------------------------------------------

    def test_migration_seeds_christmas_and_vicecity(self):
        from datetime import date
        from home.models import SeasonalEvent
        christmas = SeasonalEvent.objects.get(key='christmas')
        self.assertEqual(christmas.mode, 'auto')
        self.assertTrue(christmas.repeat_yearly)
        self.assertEqual((christmas.start_date.month, christmas.start_date.day), (12, 1))
        self.assertEqual((christmas.end_date.month, christmas.end_date.day), (1, 10))
        vice = SeasonalEvent.objects.get(key='vicecity')
        self.assertEqual(vice.mode, 'off')
        self.assertIsNone(vice.start_date)
        self.assertFalse(vice.is_active(date(2026, 12, 1)))

    def test_yearly_period_crosses_new_year(self):
        from datetime import date
        from home.models import SeasonalEvent
        event = SeasonalEvent(repeat_yearly=True, start_date=date(2000, 12, 1), end_date=date(2000, 1, 10))
        self.assertFalse(event.includes(date(2026, 11, 30)))
        self.assertTrue(event.includes(date(2026, 12, 1)))
        self.assertTrue(event.includes(date(2027, 1, 10)))
        self.assertFalse(event.includes(date(2027, 1, 11)))
        self.assertTrue(event.includes(date(2031, 12, 24)))  # l'année est ignorée

    def test_fixed_period_does_not_repeat(self):
        from datetime import date
        from home.models import SeasonalEvent
        event = SeasonalEvent(repeat_yearly=False, start_date=date(2026, 11, 19), end_date=date(2026, 12, 3))
        self.assertFalse(event.includes(date(2026, 11, 18)))
        self.assertTrue(event.includes(date(2026, 11, 19)))
        self.assertTrue(event.includes(date(2026, 12, 3)))
        self.assertFalse(event.includes(date(2026, 12, 4)))
        self.assertFalse(event.includes(date(2027, 11, 20)))

    def test_modes(self):
        from datetime import date
        from home.models import SeasonalEvent
        event = SeasonalEvent(mode='on')
        self.assertTrue(event.is_active(date(2026, 7, 1)))
        event = SeasonalEvent(mode='off', repeat_yearly=True, start_date=date(2000, 1, 1), end_date=date(2000, 12, 31))
        self.assertFalse(event.is_active(date(2026, 7, 1)))

    def test_validation(self):
        from datetime import date
        from django.core.exceptions import ValidationError
        from home.models import SeasonalEvent
        with self.assertRaises(ValidationError):  # fin avant début
            SeasonalEvent(key='vicecity', mode='auto', start_date=date(2026, 12, 3), end_date=date(2026, 11, 19)).full_clean()
        with self.assertRaises(ValidationError):  # automatique sans période
            SeasonalEvent(key='vicecity', mode='auto').full_clean()
        with self.assertRaises(ValidationError):  # une seule date
            SeasonalEvent(key='vicecity', mode='on', start_date=date(2026, 12, 3)).full_clean()
        # Période annuelle : la fin peut précéder le début (passage du 31 décembre).
        SeasonalEvent(key='christmas', mode='auto', repeat_yearly=True,
                      start_date=date(2000, 12, 1), end_date=date(2000, 1, 10)).clean()

    # --- Noël --------------------------------------------------------------

    def test_christmas_shown_during_period(self):
        response = self._get_home()
        self.assertContains(response, 'christmas/christmas.js')
        self.assertContains(response, 'xmas-trees')
        self.assertContains(response, 'Masquer le décor de Noël')

    def test_christmas_hidden_outside_period(self):
        from datetime import date
        response = self._get_home(date(2026, 11, 17))
        self.assertNotContains(response, 'christmas/christmas.js')
        self.assertNotContains(response, 'décor de Noël')

    def test_christmas_cookie_hides_decor_but_keeps_toggle(self):
        response = self._get_home(xmas_decor_off='1')
        self.assertNotContains(response, 'christmas/christmas.js')
        self.assertContains(response, 'Afficher le décor de Noël')

    def test_edited_christmas_dates_apply(self):
        from datetime import date
        self._set('christmas', start_date=date(2000, 11, 15), end_date=date(2000, 11, 20))
        self.assertContains(self._get_home(date(2026, 11, 17)), 'christmas/christmas.js')
        self.assertNotContains(self._get_home(date(2026, 12, 15)), 'christmas/christmas.js')

    # --- Bouton du footer --------------------------------------------------

    def test_toggle_switches_cookie(self):
        url = reverse('toggle_event', args=['christmas'])
        response = self.client.post(url, {'next': '/forum/'})
        self.assertRedirects(response, '/forum/', fetch_redirect_response=False)
        self.assertEqual(response.cookies['xmas_decor_off'].value, '1')
        self.client.cookies['xmas_decor_off'] = '1'
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'enabled': True})
        self.assertEqual(response.cookies['xmas_decor_off'].value, '')

        response = self.client.post(reverse('toggle_event', args=['vicecity']))
        self.assertEqual(response.cookies['vice_edition_off'].value, '1')

    def test_toggle_refuses_get_unknown_key_and_external_redirect(self):
        url = reverse('toggle_event', args=['christmas'])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(reverse('toggle_event', args=['inconnu'])).status_code, 404)
        response = self.client.post(url, {'next': 'https://exemple.com/'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    # --- Édition spéciale Vice City ----------------------------------------

    def _run_middleware(self, cookies=None, user_theme='rpg'):
        from types import SimpleNamespace
        from passion_retro.seasonal import SpecialEditionThemeMiddleware
        request = RequestFactory().get('/')
        request.COOKIES.update(cookies or {})
        request.user = SimpleNamespace(is_authenticated=True, theme=user_theme)
        request.theme_active = user_theme  # choisi par UserStatsMiddleware
        SpecialEditionThemeMiddleware(lambda r: None).process_request(request)
        return request

    def test_vice_theme_forced_during_period(self):
        self._set('vicecity', mode='on')
        request = self._run_middleware()
        self.assertEqual(request.theme_active, 'vicecity')
        self.assertEqual(request.user.theme, 'rpg')  # thème du membre intact

    def test_vice_theme_untouched_when_inactive_or_opted_out(self):
        self.assertEqual(self._run_middleware().theme_active, 'rpg')
        self._set('vicecity', mode='on')
        request = self._run_middleware(cookies={'vice_edition_off': '1'})
        self.assertEqual(request.theme_active, 'rpg')
        self.assertTrue(request.special_edition_active)
        self.assertFalse(request.special_edition_enabled)

    def test_vice_fixed_dates(self):
        from datetime import date
        from unittest import mock
        self._set('vicecity', mode='auto', start_date=date(2026, 11, 19), end_date=date(2026, 12, 3))
        with mock.patch('passion_retro.seasonal.timezone.localdate', return_value=date(2026, 11, 20)):
            self.assertEqual(self._run_middleware().theme_active, 'vicecity')
        with mock.patch('passion_retro.seasonal.timezone.localdate', return_value=date(2026, 12, 4)):
            self.assertEqual(self._run_middleware().theme_active, 'rpg')

    def test_vice_layout_and_home_banner(self):
        from passion_retro.theme_config import get_layout_config
        self.assertEqual(get_layout_config('vicecity')['menu_type'], 'horizontal')
        self._set('vicecity', mode='on')
        from django.conf import settings
        with self.settings(MIDDLEWARE=[*settings.MIDDLEWARE,
                                       'users.middleware.UserStatsMiddleware',
                                       'passion_retro.seasonal.SpecialEditionThemeMiddleware']):
            response = self._get_home()
        html = response.content.decode()
        self.assertIn('themes/vicecity/theme.css', html)
        self.assertIn('theme-vicecity', html)
        self.assertIn('vc-banner', html)
        self.assertIn('vc-event', html)
        self.assertIn('Quitter l’édition spéciale', html)

    def test_vice_toggle_stays_visible_after_opting_out(self):
        from django.conf import settings
        self._set('vicecity', mode='on')
        with self.settings(MIDDLEWARE=[*settings.MIDDLEWARE,
                                       'users.middleware.UserStatsMiddleware',
                                       'passion_retro.seasonal.SpecialEditionThemeMiddleware']):
            html = self._get_home(vice_edition_off='1').content.decode()
        self.assertNotIn('themes/vicecity/theme.css', html)
        self.assertIn(reverse('toggle_event', args=['vicecity']), html)
        self.assertIn('Réactiver l’édition spéciale', html)

    def test_wanted_stars(self):
        from types import SimpleNamespace
        from home.templatetags.vice_tags import wanted_stars
        visitor = SimpleNamespace(is_authenticated=False)
        self.assertEqual(sum(wanted_stars(visitor)), 0)
        for level, stars in ((1, 1), (10, 1), (11, 2), (26, 3), (50, 5), (99, 5)):
            user = SimpleNamespace(is_authenticated=True, level_number=level)
            self.assertEqual(sum(wanted_stars(user)), stars, level)
            self.assertEqual(len(wanted_stars(user)), 5)

    def test_vice_banner_has_vector_logo_and_hud(self):
        from django.conf import settings
        self._set('vicecity', mode='on')
        with self.settings(MIDDLEWARE=[*settings.MIDDLEWARE,
                                       'users.middleware.UserStatsMiddleware',
                                       'passion_retro.seasonal.SpecialEditionThemeMiddleware']):
            html = self._get_home().content.decode()
        self.assertIn('class="vc-logo"', html)
        self.assertIn('vc-hud__cash', html)
        self.assertIn('$0', html)  # visiteur
        # Logo figé : aucune police Pricedown chargée par le site.
        self.assertNotIn('Pricedown', html)
        self.assertNotIn('@font-face', html)

    # --- Panel ---------------------------------------------------------------

    def _staff(self):
        from users.models import User
        staff = User.objects.create_user(username='modo', email='modo@test.com', password='pass12345',
                                         active=True, is_staff=True)
        self.client.force_login(staff)

    def test_panel_is_staff_only(self):
        from users.models import User
        url = reverse('panel_seasonal')
        self.assertRedirects(self.client.get(url), reverse('home'), fetch_redirect_response=False)
        member = User.objects.create_user(username='membre', email='m@test.com', password='pass12345', active=True)
        self.client.force_login(member)
        self.assertRedirects(self.client.get(url), reverse('home'), fetch_redirect_response=False)

    def test_panel_lists_and_saves_events(self):
        from home.models import SeasonalEvent
        self._staff()
        url = reverse('panel_seasonal')
        response = self.client.get(url)
        self.assertContains(response, 'Décor de Noël')
        self.assertContains(response, 'Édition spéciale Vice City')
        response = self.client.post(url, {
            'key': 'vicecity', 'vicecity-mode': 'auto',
            'vicecity-start_date': '2026-11-19', 'vicecity-end_date': '2026-12-03',
        })
        self.assertRedirects(response, url, fetch_redirect_response=False)
        vice = SeasonalEvent.objects.get(key='vicecity')
        self.assertEqual((vice.mode, str(vice.start_date), str(vice.end_date), vice.repeat_yearly),
                         ('auto', '2026-11-19', '2026-12-03', False))
        # Noël n'a pas bougé
        self.assertEqual(SeasonalEvent.objects.get(key='christmas').mode, 'auto')

    def test_panel_rejects_invalid_period(self):
        from home.models import SeasonalEvent
        self._staff()
        response = self.client.post(reverse('panel_seasonal'), {
            'key': 'vicecity', 'vicecity-mode': 'auto',
            'vicecity-start_date': '2026-12-03', 'vicecity-end_date': '2026-11-19',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La fin doit être après le début.')
        self.assertEqual(SeasonalEvent.objects.get(key='vicecity').mode, 'off')
