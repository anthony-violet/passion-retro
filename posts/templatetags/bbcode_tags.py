from django import template
from commons.bbcode_parser import BBCodeParser
from django.utils.html import escape
from markdown import markdown

register = template.Library()


def _author_may_use_html(author):
    return bool(getattr(author, "is_staff", False) or getattr(author, "is_superuser", False))


@register.filter(name="bbcode")
def bbcode(value):
    """BBCode + HTML brut : réservé au contenu rédigé par l'équipe."""
    parser = BBCodeParser()
    return parser.parse(value)


@register.filter(name="bbcode_user")
def bbcode_user(value):
    """BBCode avec HTML échappé : contenu de membres ou de visiteurs."""
    return BBCodeParser().parse(value, allow_html=False)


@register.filter(name="bbcode_by")
def bbcode_by(value, author):
    """BBCode dont le HTML n'est conservé que si l'auteur fait partie du staff."""
    return BBCodeParser().parse(value, allow_html=_author_may_use_html(author))


@register.filter(name="markdown")
def render_markdown(value):
    return markdown(value, extensions=["extra", "nl2br"])


@register.filter(name="bbcode_or_md")
def bbcode_or_md(value):
    """BBCode ou Markdown pour du contenu de visiteurs : le HTML est échappé."""
    if not value:
        return ""
    value = escape(value)

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