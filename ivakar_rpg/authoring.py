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


# ---------------------------------------------------------------------------
# Ordre d'affichage (champ ``order``) : automatique à la création, réglé par glisser-déposer
# ---------------------------------------------------------------------------
# Modèle -> champ qui délimite sa liste (les choix d'une scène, les dialogues d'un PNJ…).
ORDER_SCOPES = {'Choice': 'scene', 'NpcDialogue': 'npc', 'LocationExit': 'from_location'}


def has_order(model):
    return any(f.name == 'order' for f in model._meta.get_fields())


def _scope(obj_or_model, obj=None):
    model = obj_or_model if isinstance(obj_or_model, type) else type(obj_or_model)
    queryset = model.objects.all()
    field = ORDER_SCOPES.get(model.__name__)
    if field and obj is not None:
        queryset = queryset.filter(**{f'{field}_id': getattr(obj, f'{field}_id')})
    return queryset


def next_order(obj):
    """Position suivant la dernière de la liste de ``obj`` (1 pour une liste vide)."""
    from django.db.models import Max

    last = _scope(obj, obj).exclude(pk=obj.pk).aggregate(m=Max('order'))['m']
    return (last or 0) + 1


def reorder(model, ids):
    """Place les éléments ``ids`` dans cet ordre, aux emplacements qu'ils occupent déjà dans la liste
    complète (les autres ne bougent pas), puis renumérote toute la liste de 1 à N."""
    ids = [int(i) for i in ids]
    everything = list(model.objects.order_by('order', 'pk').values_list('pk', flat=True))
    wanted = [pk for pk in ids if pk in set(everything)]
    slots = [index for index, pk in enumerate(everything) if pk in set(wanted)]
    for slot, pk in zip(slots, wanted):
        everything[slot] = pk
    for position, pk in enumerate(everything, start=1):
        model.objects.filter(pk=pk).exclude(order=position).update(order=position)
    return everything
