from django import template
from commons.bbcode_parser import BBCodeParser
from markdown import markdown

register = template.Library()


@register.filter(name="bbcode")
def bbcode(value):
    parser = BBCodeParser()
    return parser.parse(value)


@register.filter(name="markdown")
def render_markdown(value):
    return markdown(value, extensions=["extra", "nl2br"])


@register.filter(name="bbcode_or_md")
def bbcode_or_md(value):
    if not value:
        return ""

    has_bbcode = any(
        tag in value
        for tag in ["[b]", "[i]", "[u]", "[url]", "[img]", "[quote]", "[code]"]
    )
    has_markdown = any(char in value for char in ["#", "**", "`", "- ", ">"])

    if has_bbcode and has_markdown:
        result = value
        result = markdown(result, extensions=["extra", "nl2br"])
        parser = BBCodeParser()
        return parser.parse(result)
    elif has_bbcode:
        parser = BBCodeParser()
        return parser.parse(value)
    elif has_markdown:
        return markdown(value, extensions=["extra", "nl2br"])
    else:
        return value