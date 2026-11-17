from .models import HistoryVersion


def latest_version(request):
    """Dernière version créée, affichée dans le footer."""
    return {'latest_version': HistoryVersion.latest()}
