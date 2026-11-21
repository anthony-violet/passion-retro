from django import template

register = template.Library()


@register.filter
def field(form, name):
    """Champ ``name`` d'un formulaire (pour l'afficher dans un ordre choisi)."""
    return form[name]
