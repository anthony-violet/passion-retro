"""Hasard. Toutes les fonctions acceptent un ``random.Random`` pour des tests reproductibles."""
import random

_default_rng = random.SystemRandom()


def get_rng(rng=None):
    return rng or _default_rng


def weighted_pick(entries, rng=None):
    """``entries`` = liste de ``(poids, valeur)`` ; renvoie une valeur ou ``None``."""
    entries = [(w, v) for w, v in entries if w > 0]
    if not entries:
        return None
    total = sum(w for w, _ in entries)
    pick = get_rng(rng).randint(1, total)
    for weight, value in entries:
        pick -= weight
        if pick <= 0:
            return value
    return entries[-1][1]
