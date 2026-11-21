"""Aides à l'écriture du contenu depuis le panel : identifiants uniques, ébauches de scènes."""
from django.utils.text import slugify

from .models import Scene


def unique_slug(model, source, max_length=60):
    """Identifiant déduit de ``source``, rendu unique pour ``model`` (suffixe -2, -3…)."""
    base = slugify(source)[:max_length] or 'element'
    slug, n = base, 2
    while model.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug = f"{base[:max_length - len(suffix)]}{suffix}"
        n += 1
    return slug


def stub_scene(title, location=None, npc=None):
    """Scène en ébauche : un titre, pas encore de texte. Le panel la signale « à compléter »."""
    return Scene.objects.create(title=title[:100], slug=unique_slug(Scene, title, 80), text='', location=location,
                                npc=npc)


def is_stub(scene):
    return not (scene.text or '').strip()
