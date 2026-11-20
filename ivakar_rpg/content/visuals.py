"""Génère les illustrations de départ d'Ivakar (pixel art SVG) dans ``static/ivakar/``.

    python -m ivakar_rpg.content.visuals

Les images envoyées depuis le panel remplacent toujours ces visuels.
"""
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'static' / 'ivakar'


# ---------------------------------------------------------------------------
# Rendu : une grille de couleurs -> SVG net (une ligne de pixels = des rectangles fusionnés)
# ---------------------------------------------------------------------------
def grid_svg(grid, label, overlays=''):
    height, width = len(grid), len(grid[0])
    rects = []
    for y, row in enumerate(grid):
        x = 0
        while x < width:
            color = row[x]
            run = 1
            while x + run < width and row[x + run] == color:
                run += 1
            if color:
                rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{color}"/>')
            x += run
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="{label}" shape-rendering="crispEdges">' + ''.join(rects) + overlays + '</svg>\n')


def sprite(rows, palette, label):
    grid = [[palette.get(ch) for ch in row] for row in rows]
    return grid_svg(grid, label)


def write(folder, slug, svg):
    path = OUT / folder / f'{slug}.svg'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding='utf-8')


# ---------------------------------------------------------------------------
# Monstres (16 × 16)
# ---------------------------------------------------------------------------
K = '#16141c'  # contour
MONSTERS = {
    'gobelin-chapardeur': ("Gobelin chapardeur", {'k': K, 'g': '#5f9a3a', 'G': '#3f6e25', 'e': '#f4d03f',
                                                   'b': '#6b4a2b', 's': '#c9ccd6', 'r': '#a33'}, [
        "................",
        "....kk....kk....",
        "...kgGk..kGgk...",
        "....kgGkkGgk....",
        ".....kggggk.....",
        "....kgekkegk....",
        "....kggrrggk....",
        ".....kggggk.....",
        "....kbbbbbbk..s.",
        "...kgbbbbbbgk.s.",
        "...kgkbbbbkgkks.",
        "....k.bbbb.kk...",
        "......kbbk......",
        ".....kg..gk.....",
        ".....kk..kk.....",
        "................"]),
    'loup-gris': ("Loup gris", {'k': K, 'w': '#8d939c', 'W': '#5f646c', 'l': '#c7ccd3', 'e': '#f1c40f'}, [
        "................",
        "..k.k...........",
        "..kwkk..........",
        ".kwwwwk.........",
        "kewwwwwk........",
        "kllwwwwwkkkkkk..",
        ".kkwwwwwwwwwwwk.",
        "...kwwWWWWWwwwwk",
        "...kwwWWWWWWwwk.",
        "...kwwwwwwwwwk..",
        "...kwk.kwk.kwk..",
        "...kwk.kwk.kwk..",
        "...kk..kk..kk...",
        "................",
        "................",
        "................"]),
    'loup-alpha': ("Loup alpha", {'k': K, 'w': '#4d525b', 'W': '#33373e', 'l': '#9aa0a8', 'e': '#f1c40f',
                                  's': '#f5f5f5'}, [
        "................",
        ".k.k............",
        ".kwkk...........",
        "kwwwwk..........",
        "kewsswk.........",
        "kllwwswkkkkkkk..",
        ".kkwwwwwwwwwwwk.",
        "..kwwwWWWWWWwwwk",
        "..kwwwWWWWWWWwwk",
        "..kwwwwwwwwwwwk.",
        "..kwwk.kwwk.kwk.",
        "..kwwk.kwwk.kwk.",
        "..kkk..kkk..kk..",
        "................",
        "................",
        "................"]),
    'araignee-murmures': ("Araignée des murmures", {'k': K, 'b': '#2b2433', 'p': '#5b3f73', 'e': '#e74c3c'}, [
        "................",
        "..k..........k..",
        "...k...kk...k...",
        "k...k.kbbk.k...k",
        ".k...kbppbk...k.",
        "..kkkbbbbbbkkk..",
        "....kbpbbpbk....",
        "kkkkbbbbbbbbkkkk",
        "....kbbeebbk....",
        "..kkkbbbbbbkkk..",
        ".k...kbbbbk...k.",
        "k...k.kbbk.k...k",
        "...k...kk...k...",
        "..k..........k..",
        "................",
        "................"]),
    'sanglier-furieux': ("Sanglier furieux", {'k': K, 'b': '#6e4b2e', 'B': '#4a311d', 't': '#f2ead3',
                                               'e': '#c0392b', 'n': '#c98b6b'}, [
        "................",
        "................",
        "......kkkkkkk...",
        "..k..kbBBBBBBk..",
        ".kbkkbbbbbbbbbk.",
        "kebbbbbbbbbbbbk.",
        "kbbbbbbbbbbbbbbk",
        "knntbbbbbbbbbbbk",
        "knntkbbbbbbbbbk.",
        ".kk.kbbbbbbbbbk.",
        "....kbk.kbk.kbk.",
        "....kbk.kbk.kbk.",
        "....kk..kk..kk..",
        "................",
        "................",
        "................"]),
    'rat-geant': ("Rat géant", {'k': K, 'r': '#7d7266', 'R': '#5a5149', 'p': '#d99a9a', 'e': '#e74c3c'}, [
        "................",
        "................",
        "................",
        "....kk..........",
        "...kpRk.kkkkk...",
        "..krrrrkrrrrrk..",
        ".kerrrrrrrrrrrk.",
        "kprrrrrrrrRRrrk.",
        ".kkrrrrrrRRRrrk.",
        "...krrrrrrrrrk.k",
        "...kpk.kpk.kpkkp",
        "...kk..kk..kk..k",
        "...............k",
        "................",
        "................",
        "................"]),
    'kobold-mineur': ("Kobold mineur", {'k': K, 'r': '#b5532f', 'R': '#843a1f', 'e': '#f4d03f',
                                        'h': '#7f8c8d', 'w': '#8b5a2b', 'c': '#3d3d3d'}, [
        "................",
        ".......kk.......",
        "......kRRk.hhh..",
        ".....krrrrkhkhh.",
        ".....kerrek.kw..",
        ".....krrrrk.kw..",
        "......krrk..kw..",
        "....kkccccckkw..",
        "...krkccccckrw..",
        "...krkccccck.k..",
        "....k.ccccc.....",
        ".....kcc.cck....",
        ".....krk.krk....",
        ".....kk..kk.....",
        "................",
        "................"]),
    'squelette-garde': ("Squelette de la garde", {'k': K, 'b': '#e8e2cf', 'B': '#b9b19a', 'e': '#c0392b',
                                                   's': '#95a5a6'}, [
        "......kkkk......",
        ".....kbbbbk.....",
        ".....kekekk.....",
        ".....kbbbbk.....",
        "......kBBk...s..",
        ".....kkbbkk..s..",
        "....kbkBBkbk.s..",
        "....kbkbbkbkks..",
        "....k.kBBk.kbk..",
        "......kbbk..k...",
        "......kBBk......",
        ".....kb..bk.....",
        ".....kb..bk.....",
        ".....kb..bk.....",
        "....kkk..kkk....",
        "................"]),
    'spectre-brume': ("Spectre de brume", {'k': '#5d6d7e', 'w': '#dfe6ee', 'W': '#b8c4d0', 'e': '#1abc9c'}, [
        "................",
        ".....kkkkkk.....",
        "....kwwwwwwk....",
        "...kwwwwwwwwk...",
        "...kwweWWewwk...",
        "...kwwwwwwwwk...",
        "..kwwWwwwwWwwk..",
        ".kwwwWwwwwWwwwk.",
        ".kwwwwwwwwwwwwk.",
        "..kwwWwwwwwWwk..",
        "..kwwwwWWwwwwk..",
        "...kwwk.kwwwk...",
        "...kwk...kwk....",
        "....k.....k.....",
        "................",
        "................"]),
    'roi-brume': ("Le Roi-Brume", {'k': '#2c3e50', 'g': '#f1c40f', 'G': '#b7950b', 'w': '#cfd8e3',
                                    'W': '#94a3b8', 'e': '#5dade2', 'p': '#5b2c6f'}, [
        "....g.g.g.g.....",
        "....gGgGgGg.....",
        "....kGGGGGk.....",
        "...kwwwwwwwk....",
        "...kweewweek....",
        "...kwwwwwwwk....",
        "..kpkwwWwwkpk...",
        ".kppwwwwwwwppk..",
        ".kpwwWwwwWwwpk..",
        "kppwwwwwwwwwppk.",
        "kpwwwWwwwWwwwpk.",
        "kppwwwwwwwwwppk.",
        ".kpwwWwwwwWwpk..",
        "..kwwkwwwkwwk...",
        "..kwk.kwk.kwk...",
        "...k...k...k...."]),
}

# ---------------------------------------------------------------------------
# Objets (16 × 16)
# ---------------------------------------------------------------------------
ITEMS = {
    'baton-noueux': ("Bâton noueux", {'k': K, 'w': '#8b5a2b', 'W': '#5e3b1a'}, [
        "..............kk", ".............kwk", "............kWk.", "...........kwk..", "..........kwWk..",
        ".........kwk....", "........kWk.....", ".......kwk......", "......kwWk......", ".....kwk........",
        "....kWk.........", "...kwk..........", "..kwk...........", ".kWk............", "kwk.............",
        "kk.............."]),
    'epee-courte': ("Épée courte", {'k': K, 's': '#d5dbe3', 'S': '#9aa5b1', 'g': '#c9a227', 'w': '#6b4423'}, [
        "..............kk", ".............ksk", "............ksSk", "...........ksSk.", "..........ksSk..",
        ".........ksSk...", "........ksSk....", "...k...ksSk.....", "...kk.ksSk......", "....kgsSk.......",
        "....kggk........", "...kwkgk........", "..kwk.kk........", ".kwk............", "kgk.............",
        "kk.............."]),
    'hache-bucheron': ("Hache de bûcheron", {'k': K, 's': '#c3cad3', 'S': '#8793a0', 'w': '#7a4b22'}, [
        "................", "........kkk.....", ".......ksssk....", "......ksSSssk...", "......ksSkwkk...",
        "......kssk.kw...", ".......kk..kwk..", "...........kwk..", "............kwk.", "............kwk.",
        ".............kwk", ".............kwk", "..............kk", "................", "................",
        "................"]),
    'epee-vel-ithar': ("Lame de Vel-Ithar", {'k': K, 's': '#e8f1ff', 'S': '#7fb3ff', 'g': '#f1c40f',
                                              'b': '#3b5bdb', 'w': '#2c1e4a'}, [
        "..............kk", ".............ksk", "............ksSk", "...........ksSk.", "..........ksSk..",
        ".........ksSk...", "........ksSk....", "..k....ksSk.....", "..kgk.ksSk......", "...kgbsSk.......",
        "....kbgk........", "...kwkgk........", "..kwk.kgk.......", ".kwk...k........", "kbk.............",
        "kk.............."]),
    'veste-cuir': ("Veste de cuir", {'k': K, 'b': '#8b5a2b', 'B': '#5e3b1a', 'c': '#c9a227'}, [
        "................", "....kkk..kkk....", "...kbbbkkbbbk...", "..kbbbbBBbbbbk..", ".kbbbbbBBbbbbbk.",
        ".kbbkbbBBbbkbbk.", ".kbk.kbcBbk.kbk.", ".kbk.kbBBbk.kbk.", ".kk..kbcBbk..kk.", ".....kbBBbk.....",
        ".....kbcBbk.....", ".....kbBBbk.....", ".....kkkkkk.....", "................", "................",
        "................"]),
    'cotte-mailles': ("Cotte de mailles", {'k': K, 'm': '#aab3bd', 'M': '#7b8591'}, [
        "................", "....kkk..kkk....", "...kmMmkkmMmk...", "..kmMmMmMmMmMk..", ".kmMmMmMmMmMmMk.",
        ".kMmkMmMmMmkMmk.", ".kmk.kMmMmk.kmk.", ".kMk.kmMmMk.kMk.", ".kk..kMmMmk..kk.", ".....kmMmMk.....",
        ".....kMmMmk.....", ".....kmMmMk.....", ".....kkkkkk.....", "................", "................",
        "................"]),
    'amulette-brumes': ("Amulette des brumes", {'k': K, 'g': '#c9a227', 'c': '#7fd3e0', 'C': '#3fa7b8'}, [
        "................", "...kk......kk...", "...kgk....kgk...", "....kgk..kgk....", ".....kgkkgk.....",
        "......kggk......", ".....kgggk......", "....kgcccgk.....", "...kgcCcccgk....", "...kgccCccgk....",
        "...kgcccCcgk....", "....kgcccgk.....", ".....kgggk......", "......kkk.......", "................",
        "................"]),
    'pain': ("Miche de pain", {'k': K, 'b': '#d4a056', 'B': '#a8742f', 'l': '#ecc98a'}, [
        "................", "................", "................", "................", ".....kkkkkk.....",
        "...kkbllbblkk...", "..kblbBbbBblbk..", ".kbbbbBbbBbbbbk.", ".kbBbbbbbbbbBbk.", ".kbbbbbbbbbbbbk.",
        ".kBBBBBBBBBBBBk.", "..kkkkkkkkkkkk..", "................", "................", "................",
        "................"]),
    'potion-soin': ("Potion de soin", {'k': K, 'g': '#d6eaf8', 'r': '#e74c3c', 'R': '#a93226', 'c': '#8b5a2b'}, [
        "................", "......kkkk......", "......kcck......", "......kggk......", ".....kggggk.....",
        "....kggggggk....", "...kgrrrrrrgk...", "...krrrRrrrrk...", "...krrrrrRrrk...", "...krRrrrrrrk...",
        "...krrrrrrRrk...", "....krrrrrrk....", ".....kkkkkk.....", "................", "................",
        "................"]),
    'grande-potion': ("Grande potion de soin", {'k': K, 'g': '#d6eaf8', 'r': '#c0392b', 'R': '#7b241c',
                                                 'c': '#c9a227'}, [
        "......kkkk......", "......kcck......", "......kggk......", ".....kggggk.....", "....kggggggk....",
        "...kggggggggk...", "..kgrrrrrrrrgk..", "..krrrRrrrrrrk..", "..krrrrrrRrrrk..", "..krRrrrrrrrrk..",
        "..krrrrrRrrrrk..", "..krrrrrrrrRrk..", "...krrrrrrrrk...", "....kkkkkkkk....", "................",
        "................"]),
    'lanterne': ("Lanterne à huile", {'k': K, 'm': '#6c757d', 'y': '#f9e79f', 'Y': '#f4d03f'}, [
        ".......kk.......", "......k..k......", "......k..k......", ".....kmmmmk.....", "....kmmmmmmk....",
        "....kmyyyymk....", "....kmyYYymk....", "....kmyYYymk....", "....kmyYYymk....", "....kmyyyymk....",
        "....kmmmmmmk....", ".....kmmmmk.....", "......kkkk......", "................", "................",
        "................"]),
    'soie-araignee': ("Soie d'araignée", {'k': '#9aa5b1', 'w': '#f4f6f7'}, [
        "................", "k......k......k.", ".k.....k.....k..", "..k..wwkww..k...", "...kw..k..wk....",
        "...wk..k..kw....", "..w..k.k.k..w...", "kkkkkkkkkkkkkkk.", "..w..k.k.k..w...", "...wk..k..kw....",
        "...kw..k..wk....", "..k..wwkww..k...", ".k.....k.....k..", "k......k......k.", "................",
        "................"]),
    'croc-alpha': ("Croc de l'alpha", {'k': K, 'w': '#f2ead3', 'W': '#cbbf9c', 'c': '#8b5a2b'}, [
        "................", "...kkkkkkkkkk...", "...kccccccccck..", "....kwwwwwwwk...", "....kwwwwwwWk...",
        ".....kwwwwWk....", ".....kwwwwWk....", "......kwwWk.....", "......kwwWk.....", ".......kwk......",
        ".......kwk......", "........k.......", "................", "................", "................",
        "................"]),
    'cle-runique': ("Clé runique", {'k': K, 's': '#5d8aa8', 'S': '#3b5f78', 'c': '#7fd3e0'}, [
        "................", "...kkkk.........", "..ksSSsk........", ".ksckkcsk.......", ".ksk..ksk.......",
        ".ksckkcsk.......", "..ksSSskkkkkkkk.", "...kkkkssssssssk", ".......kSSSSkSSk", "...........k.kk.",
        "...........kck..", "............k...", "................", "................", "................",
        "................"]),
}


# ---------------------------------------------------------------------------
# Lieux (96 × 54) : paysages peints sur une grille
# ---------------------------------------------------------------------------
W, H = 96, 54


def blank():
    return [[None] * W for _ in range(H)]


def paint(grid, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        grid[y][x] = color


def rect(grid, x0, y0, x1, y1, color):
    for y in range(y0, y1):
        for x in range(x0, x1):
            paint(grid, x, y, color)


def sky(grid, colors, until=H):
    band = max(1, until // len(colors))
    for y in range(until):
        color = colors[min(len(colors) - 1, y // band)]
        for x in range(W):
            grid[y][x] = color


def hills(grid, base, amplitude, period, phase, color, seed=0):
    rng = random.Random(seed)
    for x in range(W):
        top = int(base + amplitude * math.sin(x / period + phase) + rng.choice((0, 0, 1)))
        for y in range(max(0, top), H):
            grid[y][x] = color


def pine(grid, x, base, height, color, trunk='#3b2a1a'):
    for i in range(height):
        half = i // 2
        for dx in range(-half, half + 1):
            paint(grid, x + dx, base - height + i, color)
    paint(grid, x, base, trunk)
    paint(grid, x, base + 1, trunk)


def house(grid, x, base, width, height, wall, roof, window='#f9d56e'):
    rect(grid, x, base - height, x + width, base, wall)
    for i in range(width // 2 + 2):
        rect(grid, x - 1 + i, base - height - i, x + width + 1 - i, base - height - i + 1, roof)
    paint(grid, x + 1, base - height + 2, window)
    paint(grid, x + width - 2, base - height + 2, window)
    rect(grid, x + width // 2, base - 3, x + width // 2 + 2, base, '#3b2a1a')


def mist(opacity_rows, color='#e8edf2'):
    return ''.join(f'<rect x="0" y="{y}" width="{W}" height="{h}" fill="{color}" opacity="{o}"/>'
                   for y, h, o in opacity_rows)


def location_precalm():
    """Bourgade des plaines d'Agasur, sans rempart ni garde."""
    g = blank()
    sky(g, ['#8fa6b8', '#a3b7c6', '#b8c8d3', '#c9d5dd'], 30)
    hills(g, 27, 1, 14, 0.5, '#8a9a6a', 1)
    hills(g, 32, 1, 9, 2.0, '#7d9156', 2)
    rect(g, 0, 40, W, H, '#6f7f45')
    rect(g, 26, 41, 70, 46, '#a08a62')
    for x in range(0, 26, 3):
        paint(g, x, 44 + (x % 2), '#8a9a5a')
    house(g, 8, 41, 9, 6, '#c9b38a', '#8e3b2b')
    house(g, 22, 41, 11, 7, '#d8c49b', '#6d2f22')
    house(g, 40, 41, 14, 9, '#d8c49b', '#7a3326')
    house(g, 60, 41, 10, 6, '#c9b38a', '#8e3b2b')
    house(g, 76, 41, 12, 8, '#cdb68e', '#6d2f22')
    rect(g, 56, 30, 58, 41, '#5a4630')
    for y in range(22, 30):
        paint(g, 57 + (y % 2), y, '#9aa0a6')
    rect(g, 70, 46, 73, 50, '#5a4630')
    rect(g, 69, 45, 74, 46, '#7a5a3a')
    return grid_svg(g, "Précalm", mist([(18, 5, .3), (30, 4, .2)]))


def location_lisiere():
    g = blank()
    sky(g, ['#9aaab5', '#aebbc4', '#c2ccd2'], 26)
    hills(g, 24, 2, 7, 1.0, '#6f8573', 3)
    rect(g, 0, 38, W, H, '#4f6b3b')
    rng = random.Random(4)
    for i in range(14):
        x = 4 + i * 7 + rng.randint(-1, 1)
        pine(g, x, 37 + rng.randint(0, 3), 10 + rng.randint(0, 6), rng.choice(['#2f4a2c', '#36553a', '#28402a']))
    for x in range(30, 70):
        paint(g, x, 46 + int(2 * math.sin(x / 6)), '#8a7a5c')
        paint(g, x, 47 + int(2 * math.sin(x / 6)), '#8a7a5c')
    for x, y in ((20, 44), (60, 49), (75, 43)):
        paint(g, x, y, '#cfe3ff')
        paint(g, x + 1, y, '#8fb8f0')
    return grid_svg(g, "La Lisière brumeuse", mist([(20, 8, .4), (34, 6, .3), (44, 4, .2)]))


def location_foret():
    g = blank()
    sky(g, ['#55665a', '#4b5c50', '#415247'], 54)
    rng = random.Random(7)
    for layer, (color, top) in enumerate((('#2f4535', 6), ('#263a2c', 10), ('#1d2e22', 14))):
        for i in range(10):
            x = rng.randint(0, W)
            rect(g, x, top, x + 4 + layer, H, color)
    rect(g, 0, 44, W, H, '#2b3b25')
    for i in range(30):
        x, y = rng.randint(0, W - 1), rng.randint(44, H - 1)
        paint(g, x, y, '#3f5a33')
    for x, y in ((40, 47), (52, 49), (66, 46)):
        paint(g, x, y, '#7fd3e0')
    return grid_svg(g, "La Forêt des Murmures", mist([(24, 10, .25), (40, 8, .3)], '#b9d1c2'))


def location_mine():
    g = blank()
    sky(g, ['#b0b8c0', '#c3c9cf'], 18)
    hills(g, 10, 5, 8, 0.2, '#6b6157', 5)
    hills(g, 20, 3, 5, 1.4, '#574e45', 6)
    rect(g, 0, 42, W, H, '#4a423a')
    for y in range(22, 44):
        half = min(12, (y - 22) // 1 + 3)
        for x in range(48 - half, 48 + half):
            paint(g, x, y, '#0f0d0c')
    rect(g, 34, 22, 36, 44, '#7a4b22')
    rect(g, 60, 22, 62, 44, '#7a4b22')
    rect(g, 33, 20, 63, 23, '#7a4b22')
    for x in range(10, 90):
        if x % 4 in (0, 1):
            paint(g, x, 48, '#8a8a8a')
        paint(g, x, 46, '#5c5c5c')
        paint(g, x, 50, '#5c5c5c')
    rect(g, 70, 39, 80, 45, '#6b4a2b')
    paint(g, 72, 46, K)
    paint(g, 78, 46, K)
    rect(g, 46, 30, 50, 34, '#f4d03f')
    return grid_svg(g, "La Mine abandonnée", mist([(16, 4, .2)]))


def location_ruines():
    g = blank()
    sky(g, ['#7d8a99', '#909cab', '#a5afbc', '#b7c0ca'], 34)
    hills(g, 34, 2, 10, 0.0, '#5e6b62', 8)
    rect(g, 0, 42, W, H, '#5b5d58')
    for x, h in ((10, 22), (22, 14), (34, 26), (62, 18), (74, 24), (86, 10)):
        rect(g, x, 42 - h, x + 4, 42, '#b9b4a7')
        rect(g, x - 1, 42 - h, x + 5, 42 - h + 2, '#d2cdbf')
        rect(g, x + 3, 42 - h + 3, x + 4, 42, '#8f8a7e')
    rect(g, 40, 30, 58, 42, '#8f8a7e')
    rect(g, 44, 34, 54, 42, '#1d1b22')
    rect(g, 38, 28, 60, 30, '#b9b4a7')
    for x in range(44, 54, 2):
        paint(g, x, 40, '#7fb3ff')
    return grid_svg(g, "Les Ruines de Vel-Ithar", mist([(18, 8, .35), (30, 6, .35), (40, 4, .3)]))


def location_crypte():
    g = blank()
    sky(g, ['#14121a', '#1b1822', '#221e2b'], 54)
    for x in range(0, W, 12):
        rect(g, x, 0, x + 3, 44, '#2e2a38')
    rect(g, 0, 44, W, H, '#2a2631')
    rect(g, 38, 22, 58, 44, '#0c0b10')
    rect(g, 36, 16, 40, 44, '#0c0b10')
    rect(g, 56, 16, 60, 44, '#0c0b10')
    for y in range(24, 42):
        width = 4 + (y - 24) // 3
        rect(g, 48 - width // 2, y, 48 + width // 2, y + 1, '#cfd8e3')
    paint(g, 46, 27, '#5dade2')
    paint(g, 49, 27, '#5dade2')
    for x in range(45, 52, 2):
        paint(g, x, 22, '#f1c40f')
    for x in (12, 84):
        rect(g, x, 30, x + 2, 34, '#5dade2')
    return grid_svg(g, "La Crypte du Roi-Brume", mist([(30, 14, .2)], '#9fb3c8'))


LOCATIONS = {
    'precalm': location_precalm,
    'lisiere': location_lisiere,
    'foret-murmures': location_foret,
    'mine-abandonnee': location_mine,
    'ruines-vel-ithar': location_ruines,
    'crypte-roi-brume': location_crypte,
}


# ---------------------------------------------------------------------------
# Carte du monde : parchemin (vectoriel, 1000 × 700)
# ---------------------------------------------------------------------------
def parchment():
    rng = random.Random(11)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="0 0 1000 700" role="img" '
        'aria-label="Carte des plaines d’Agasur" preserveAspectRatio="none">',
        '<defs><radialGradient id="v" cx="50%" cy="50%" r="70%"><stop offset="55%" stop-color="#e9d8b0"/>'
        '<stop offset="100%" stop-color="#b8955c"/></radialGradient>'
        '<filter id="n"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3"/>'
        '<feColorMatrix values="0 0 0 0 .35  0 0 0 0 .25  0 0 0 0 .12  0 0 0 .12 0"/></filter></defs>',
        '<rect width="1000" height="700" fill="url(#v)"/>',
        '<rect width="1000" height="700" filter="url(#n)"/>',
        '<rect x="14" y="14" width="972" height="672" fill="none" stroke="#6b4a2b" stroke-width="3"/>',
        '<rect x="22" y="22" width="956" height="656" fill="none" stroke="#6b4a2b" stroke-width="1"/>',
    ]
    # Mer à l'est et au sud
    parts.append('<path d="M1000 380 C930 400 900 470 930 540 C950 600 900 650 820 700 L1000 700Z" '
                 'fill="#9fb8b8" opacity=".55"/>')
    parts.append('<path d="M930 395 C905 440 905 480 932 535" fill="none" stroke="#5b7a7a" stroke-width="2" '
                 'stroke-dasharray="6 6"/>')
    # Rivière
    parts.append('<path d="M640 20 C620 120 690 200 640 300 C600 380 520 430 480 520 C450 590 470 650 450 700" '
                 'fill="none" stroke="#6f9aa0" stroke-width="7" opacity=".8"/>')
    # Montagnes à l'ouest
    for i in range(16):
        x = 60 + (i % 6) * 45 + rng.randint(-10, 10)
        y = 170 + (i // 6) * 90 + rng.randint(-15, 15)
        s = rng.randint(28, 42)
        parts.append(f'<path d="M{x - s} {y + s} L{x} {y - s} L{x + s} {y + s}" fill="#c9b48a" stroke="#5a4630" '
                     'stroke-width="2.5" stroke-linejoin="round"/>')
        parts.append(f'<path d="M{x} {y - s} L{x + s // 3} {y} L{x + s // 6} {y + s // 3}" fill="none" '
                     'stroke="#5a4630" stroke-width="1.5"/>')
    # Forêt au centre-nord
    for i in range(70):
        x = rng.randint(420, 720)
        y = rng.randint(250, 480)
        if (x - 570) ** 2 / 160 ** 2 + (y - 370) ** 2 / 115 ** 2 > 1:
            continue
        parts.append(f'<circle cx="{x}" cy="{y}" r="11" fill="#7d8f5a" stroke="#3f4a2a" stroke-width="2"/>')
        parts.append(f'<line x1="{x}" y1="{y + 10}" x2="{x}" y2="{y + 17}" stroke="#3f4a2a" stroke-width="2"/>')
    # Lisière : arbres épars
    for i in range(18):
        x, y = rng.randint(330, 470), rng.randint(470, 580)
        parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#93a36a" stroke="#3f4a2a" stroke-width="1.8"/>')
    # Ruines au nord-est
    for i in range(6):
        x = 720 + i * 18
        h = rng.randint(16, 34)
        parts.append(f'<rect x="{x}" y="{200 - h}" width="9" height="{h}" fill="#d8ccb0" stroke="#5a4630" '
                     'stroke-width="2"/>')
    # Champs autour du village
    for i in range(5):
        x, y = 210 + i * 30, 740 - 80 - (i % 2) * 25
        parts.append(f'<rect x="{x}" y="{y - 70}" width="26" height="20" fill="none" stroke="#8a6a3a" '
                     'stroke-width="1.5" transform="rotate(-8 {x} {y})"/>')
    # Rose des vents
    cx, cy = 900, 110
    parts.append(f'<g transform="translate({cx} {cy})" stroke="#5a4630" stroke-width="2">'
                 '<circle r="42" fill="none"/><circle r="5" fill="#5a4630"/>'
                 '<path d="M0 -60 L9 0 L0 60 L-9 0Z" fill="#c9a96b"/>'
                 '<path d="M-60 0 L0 -9 L60 0 L0 9Z" fill="#e9d8b0"/></g>')
    parts.append(f'<text x="{cx}" y="{cy - 66}" text-anchor="middle" font-family="Georgia, serif" font-size="22" '
                 'fill="#5a4630">N</text>')
    # Cartouche
    parts.append('<g font-family="Georgia, serif" fill="#4a3520">'
                 '<rect x="40" y="590" width="300" height="70" fill="#efe1bd" stroke="#6b4a2b" stroke-width="2"/>'
                 '<text x="190" y="622" text-anchor="middle" font-size="24" font-style="italic">'
                 'Les plaines d’Agasur</text>'
                 '<text x="190" y="646" text-anchor="middle" font-size="14">Ivakar</text></g>')
    parts.append('</svg>\n')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Portraits de PNJ (16 × 16) : un buste dessiné à partir de quelques réglages
# ---------------------------------------------------------------------------
def portrait(label, skin, hair, clothes, background, hair_style='short', beard=None, accent=None):
    g = [[background] * 16 for _ in range(16)]

    def put(x, y, color):
        if 0 <= x < 16 and 0 <= y < 16 and color:
            g[y][x] = color

    # Épaules et vêtement
    for y in range(12, 16):
        for x in range(2 + (15 - y) // 2, 14 - (15 - y) // 2):
            put(x, y, clothes)
    for x in range(6, 10):
        put(x, 12, skin)  # cou
    if accent:
        for y in range(13, 16):
            put(7, y, accent)
            put(8, y, accent)
    # Visage
    for y in range(4, 12):
        for x in range(5, 11):
            put(x, y, skin)
    for x in (6, 9):
        put(x, 7, K)  # yeux
    put(7, 10, '#8a4b3a')
    put(8, 10, '#8a4b3a')  # bouche
    # Cheveux
    for x in range(5, 11):
        put(x, 3, hair)
    for x in range(4, 12):
        put(x, 4, hair)
    put(4, 5, hair)
    put(11, 5, hair)
    if hair_style == 'long':
        for y in range(5, 13):
            put(4, y, hair)
            put(11, y, hair)
        for x in range(5, 11):
            put(x, 5, hair)
    elif hair_style == 'hood':
        for y in range(2, 13):
            put(3, y, hair)
            put(12, y, hair)
        for x in range(4, 12):
            put(x, 2, hair)
    if beard:
        for y in range(9, 14):
            for x in range(5 + max(0, y - 11), 11 - max(0, y - 11)):
                put(x, y, beard)
        put(7, 10, '#8a4b3a')
        put(8, 10, '#8a4b3a')
    return grid_svg(g, label)


PORTRAITS = {
    'maela': lambda: portrait("Maela, aubergiste", '#e8b88f', '#8b3a1e', '#5b6e3a', '#f1e3c8', 'long',
                              accent='#efe6d2'),
    'tobald': lambda: portrait("Tobald, ermite", '#d9a77f', '#6b5b4a', '#4a5a3a', '#dfe8d6', 'hood',
                               beard='#d8d4cc'),
    'inconnu': lambda: portrait("Personnage", '#d9a77f', '#3b3540', '#55606e', '#e4e4e8', 'hood'),
}


def main():
    for slug, painter in PORTRAITS.items():
        write('pnj', slug, painter())
    for slug, (label, palette, rows) in MONSTERS.items():
        assert all(len(r) == 16 for r in rows) and len(rows) == 16, slug
        write('monstres', slug, sprite(rows, palette, label))
    for slug, (label, palette, rows) in ITEMS.items():
        assert all(len(r) == 16 for r in rows) and len(rows) == 16, slug
        write('objets', slug, sprite(rows, palette, label))
    for slug, painter in LOCATIONS.items():
        write('lieux', slug, painter())
    (OUT / 'carte').mkdir(parents=True, exist_ok=True)
    (OUT / 'carte' / 'parchemin.svg').write_text(parchment(), encoding='utf-8')
    print(f"Illustrations écrites dans {OUT}")


if __name__ == '__main__':
    main()
