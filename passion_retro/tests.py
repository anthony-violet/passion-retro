from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, override_settings

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
