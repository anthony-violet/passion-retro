from django.test import TestCase
from commons.bbcode_parser import BBCodeParser


class BBCodeParserTest(TestCase):
    def setUp(self):
        self.parser = BBCodeParser()

    def test_bold(self):
        result = self.parser.parse("[b]Hello[/b]")
        self.assertEqual(result, "<strong>Hello</strong>")

    def test_italic(self):
        result = self.parser.parse("[i]Hello[/i]")
        self.assertEqual(result, "<i>Hello</i>")

    def test_underline(self):
        result = self.parser.parse("[u]Hello[/u]")
        self.assertEqual(result, "<u>Hello</u>")

    def test_strike(self):
        result = self.parser.parse("[s]Hello[/s]")
        self.assertEqual(result, "<strike>Hello</strike>")

    def test_url_with_text(self):
        result = self.parser.parse("[url=https://example.com]Click[/url]")
        self.assertEqual(result, '<a href="https://example.com">Click</a>')

    def test_url_without_text(self):
        result = self.parser.parse("[url]https://example.com[/url]")
        self.assertEqual(
            result, '<a href="https://example.com">https://example.com</a>'
        )

    def test_img(self):
        result = self.parser.parse("[img]https://example.com/image.png[/img]")
        self.assertIn('src="https://example.com/image.png"', result)
        self.assertIn("<img", result)

    def test_img_with_alt(self):
        result = self.parser.parse("[img alt=photo]https://example.com/image.png[/img]")
        self.assertIn('src="https://example.com/image.png"', result)
        self.assertIn('alt="photo"', result)

    def test_list(self):
        result = self.parser.parse("[list]item[/list]")
        self.assertIn('<ul class="bbcode-list">', result)
        self.assertIn("item", result)

    def test_list_items_wrap_their_text(self):
        result = self.parser.parse("[list]\n[*][b]GTA IV[/b] : 500 M$\n[*][b]GTA V[/b] : 1 Md$\n[/list]")
        self.assertEqual(
            result,
            '<ul class="bbcode-list">'
            '<li class="bbcode-list"><strong>GTA IV</strong> : 500 M$</li>'
            '<li class="bbcode-list"><strong>GTA V</strong> : 1 Md$</li>'
            '</ul>',
        )

    def test_nested_lists(self):
        result = self.parser.parse("[list][*]Sega[list][*]Game Gear[*]Nomad[/list][*]Nintendo[/list]")
        self.assertEqual(
            result,
            '<ul class="bbcode-list">'
            '<li class="bbcode-list">Sega<ul class="bbcode-list">'
            '<li class="bbcode-list">Game Gear</li><li class="bbcode-list">Nomad</li></ul></li>'
            '<li class="bbcode-list">Nintendo</li>'
            '</ul>',
        )

    def test_list_item(self):
        result = self.parser.parse("[*]item")
        self.assertIn('<li class="bbcode-list">', result)

    def test_heading_t1(self):
        result = self.parser.parse("[t1]Title[/t1]")
        self.assertIn("font-size:2rem", result)
        self.assertIn("Title", result)

    def test_heading_t2(self):
        result = self.parser.parse("[t2]Title[/t2]")
        self.assertIn("font-size:1.6rem", result)

    def test_heading_t3(self):
        result = self.parser.parse("[t3]Title[/t3]")
        self.assertIn("font-size:1.4rem", result)

    def test_quote(self):
        result = self.parser.parse("[quote]Some text[/quote]")
        self.assertIn('class="quote-bbcode"', result)
        self.assertIn("Some text", result)

    def test_quote_with_author(self):
        result = self.parser.parse("[quote=John]Some text[/quote]")
        self.assertIn("<legend>John</legend>", result)
        self.assertIn("Some text", result)

    def test_citation(self):
        result = self.parser.parse("[citation]Some text[/citation]")
        self.assertIn('class="quote-bbcode"', result)

    def test_citation_with_author(self):
        result = self.parser.parse("[citation=John]Some text[/citation]")
        self.assertIn("<legend>John</legend>", result)

    def test_color(self):
        result = self.parser.parse("[color=red]Text[/color]")
        self.assertIn("color: red;", result)

    def test_size(self):
        result = self.parser.parse("[size=20]Text[/size]")
        self.assertIn("font-size: 20px;", result)

    def test_paragraph(self):
        result = self.parser.parse("[p]Text[/p]")
        self.assertEqual(result, "<p>Text</p>")

    def test_center(self):
        result = self.parser.parse("[center]Text[/center]")
        self.assertIn("text-align:center", result)

    def test_right(self):
        result = self.parser.parse("[right]Text[/right]")
        self.assertIn("text-align:right", result)

    def test_hr(self):
        result = self.parser.parse("[hr]")
        self.assertEqual(result, "<hr>")

    def test_block(self):
        result = self.parser.parse("[block]Content[/block]")
        self.assertEqual(result, "<div>Content</div>")

    def test_block_with_style(self):
        result = self.parser.parse("[block style=color:red]Content[/block]")
        self.assertIn('style="color:red"', result)

    def test_block_with_class(self):
        result = self.parser.parse("[block class=my-class]Content[/block]")
        self.assertIn('class="my-class"', result)

    def test_code(self):
        result = self.parser.parse('[code]print("hello")[/code]')
        self.assertIn("<pre", result)
        self.assertIn("<code", result)
        self.assertIn("print", result)

    def test_code_with_language(self):
        result = self.parser.parse('[code=python]print("hello")[/code]')
        self.assertIn("language-python", result)

    def test_code_escapes_html(self):
        result = self.parser.parse('[code]<script>alert("xss")[/code]')
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)

    def test_nested_bold_italic(self):
        result = self.parser.parse("[b][i]Bold Italic[/i][/b]")
        self.assertIn("<strong>", result)
        self.assertIn("<i>", result)

    def test_multiple_tags(self):
        result = self.parser.parse("[b]Bold[/b] and [i]italic[/i]")
        self.assertIn("<strong>Bold</strong>", result)
        self.assertIn("<i>italic</i>", result)

    def test_plain_text_unchanged(self):
        text = "Just plain text without any BBCode"
        result = self.parser.parse(text)
        self.assertEqual(result, text)
