from .models import Memory


def pending_memories_count(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_staff:
        return {'pending_memories_count': 0}
    return {
        'pending_memories_count': Memory.objects.filter(status=Memory.STATUS_PENDING).count()
    }


def _random_published_memory():
    import random

    ids = list(
        Memory.objects.filter(status=Memory.STATUS_PUBLISHED).values_list('pk', flat=True)
    )
    if not ids:
        return None
    return Memory.objects.select_related('author').get(pk=random.choice(ids))


def wall_widget(request):
    """Souvenir au hasard pour l'encart de la colonne de droite.

    Fourni sous forme de fonction : le template ne déclenche la requête que
    s'il affiche réellement l'encart.
    """
    return {'wall_random_memory': _random_published_memory}
