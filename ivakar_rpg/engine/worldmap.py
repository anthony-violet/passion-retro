"""Carte du monde : lieux placés, chemins et brouillard de guerre."""
from ..models import LocationExit, Location
from .character import owned_item_ids
from .world import exit_lock_reason


def known_location_ids(character):
    """Lieux visités et leurs voisins directs (le reste reste dans le brouillard)."""
    visited = set(character.visited or [])
    if character.location_id:
        visited.add(character.location_id)
    neighbours = set(LocationExit.objects.filter(from_location_id__in=visited).values_list('to_location_id',
                                                                                             flat=True))
    return visited, visited | neighbours


def map_for(character=None):
    """Repères et chemins à dessiner. Sans héros (panel), toute la carte est visible."""
    locations = {loc.pk: loc for loc in Location.objects.exclude(map_x=None).exclude(map_y=None)}
    if character is None:
        visited = known = set(locations)
    else:
        visited, known = known_location_ids(character)

    exits = list(LocationExit.objects.select_related('to_location', 'required_item'))
    owned = owned_item_ids(character) if character else set()
    moves = {}
    if character is not None and not character.is_ko and not character.scene_id:
        for exit in exits:
            if exit.from_location_id == character.location_id:
                moves[exit.to_location_id] = (exit, exit_lock_reason(character, exit, owned))

    markers = []
    for pk, loc in locations.items():
        if pk not in known:
            continue
        exit, reason = moves.get(pk, (None, None))
        markers.append({
            'location': loc,
            'x': loc.map_x / 10, 'y': loc.map_y / 10,  # pourcentages
            'visited': pk in visited,
            'current': character is not None and pk == character.location_id,
            'exit': exit,
            'lock_reason': reason,
        })

    seen_pairs, paths = set(), []
    for exit in exits:
        a, b = exit.from_location_id, exit.to_location_id
        if a not in locations or b not in locations or (a, b) in seen_pairs or (b, a) in seen_pairs:
            continue
        if a not in visited and b not in visited:
            continue
        if a not in known or b not in known:
            continue
        seen_pairs.add((a, b))
        paths.append({'a': a, 'b': b, 'x1': locations[a].map_x, 'y1': locations[a].map_y,
                      'x2': locations[b].map_x, 'y2': locations[b].map_y,
                      'explored': a in visited and b in visited})
    return {'markers': markers, 'paths': paths}
