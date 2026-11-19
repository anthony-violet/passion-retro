"""Sécurité du rendu BBCode : HTML échappé pour les membres, URL dangereuses neutralisées."""

from django.template import Context, Template
from django.test import TestCase

from commons.bbcode_parser import BBCodeParser
from users.models import User


class BBCodeEscapingTest(TestCase):
    def setUp(self):
        self.parser = BBCodeParser()

    def test_user_html_is_escaped(self):
        result = self.parser.parse('<script>alert(1)</script>[b]ok[/b]', allow_html=False)
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertIn('<strong>ok</strong>', result)

    def test_attribute_breakout_is_impossible(self):
        result = self.parser.parse('[url=http://a.fr" onmouseover="alert(1)]x[/url]', allow_html=False)
        self.assertNotIn('" onmouseover="', result)

    def test_img_onerror_is_escaped(self):
        result = self.parser.parse('<img src=x onerror=alert(1)>', allow_html=False)
        self.assertNotIn('<img src=x', result)

    def test_javascript_urls_neutralised(self):
        for payload in ('[url=javascript:alert(1)]x[/url]', '[url]javascript:alert(1)[/url]',
                        '[url= JaVaScRiPt:alert(1)]x[/url]', '[img]javascript:alert(1)[/img]',
                        '[url=data:text/html;base64,AAA]x[/url]'):
            for allow_html in (True, False):
                with self.subTest(payload=payload, allow_html=allow_html):
                    result = self.parser.parse(payload, allow_html=allow_html)
                    self.assertNotIn('javascript:', result.lower().replace(' ', ''))
                    self.assertNotIn('data:', result)

    def test_safe_urls_kept(self):
        for url in ('https://passion-retro.com', 'http://a.fr/x?y=1', '/forum/', 'mailto:a@b.fr', 'page.html'):
            with self.subTest(url=url):
                self.assertIn(f'href="{url}"', self.parser.parse(f'[url={url}]x[/url]', allow_html=False))

    def test_color_and_size_cannot_inject_css(self):
        result = self.parser.parse('[color=red;position:fixed]x[/color][size=10;top:0]y[/size]', allow_html=False)
        self.assertNotIn('position:fixed', result.replace(' ', ''))
        self.assertNotIn('top:0', result.replace(' ', ''))

    def test_code_block_still_escaped_once(self):
        result = self.parser.parse('[code]<b>&</b>[/code]', allow_html=False)
        self.assertIn('&lt;b&gt;&amp;&lt;/b&gt;', result)
        self.assertNotIn('&amp;lt;', result)

    def test_staff_html_is_preserved(self):
        result = self.parser.parse('<center>Hello</center>')
        self.assertIn('<center>Hello</center>', result)


class BBCodeFiltersTest(TestCase):
    def render(self, template, **context):
        return Template('{% load bbcode_tags %}' + template).render(Context(context))

    def test_bbcode_by_escapes_members(self):
        member = User.objects.create_user(username='m', password='p')
        html = self.render('{{ v|bbcode_by:a|safe }}', v='<script>x</script>', a=member)
        self.assertNotIn('<script>', html)

    def test_bbcode_by_keeps_staff_html(self):
        staff = User.objects.create_user(username='s', password='p', is_staff=True)
        html = self.render('{{ v|bbcode_by:a|safe }}', v='<center>x</center>', a=staff)
        self.assertIn('<center>x</center>', html)

    def test_bbcode_user_escapes(self):
        html = self.render('{{ v|bbcode_user|safe }}', v='<script>x</script>')
        self.assertNotIn('<script>', html)

    def test_bbcode_or_md_escapes(self):
        for value in ('<script>x</script>', '**gras** <script>x</script>', '[b]a[/b]<script>x</script>'):
            with self.subTest(value=value):
                self.assertNotIn('<script>', self.render('{{ v|bbcode_or_md|safe }}', v=value))
