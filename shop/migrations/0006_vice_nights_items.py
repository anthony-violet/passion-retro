"""Collection « Vice Nights » : objets inspirés de GTA 6 et de l'édition spéciale Vice Nights.

Inspiration uniquement : aucun logo ni visuel officiel. Les styles des cadres et
pseudos sont dans static/themes/border-avatars.css et decoration-username.css.
Le thème Vice Nights reste une édition spéciale temporaire et n'est pas vendu.
"""
from django.db import migrations

CATEGORY = 'Vice Nights'

ITEMS = [
    # (css_class, nom, type, rareté, prix, stock, effet, description)
    ('cadre-vice-beach', 'Cadre Vice Beach', 'frame', 'rare', 220, None, '',
     "Un coucher de soleil rose et orangé sur l'océan, comme une fin de journée à Vice Beach."),
    ('cadre-leonida-neon', 'Cadre Néons de Leonida', 'frame', 'epic', 320, None, '',
     "Double néon rose et turquoise qui grésille, palmier compris. Ambiance Ocean Drive à 2 h du matin."),
    ('cadre-wanted', 'Cadre Avis de recherche', 'frame', 'legendary', 500, 30, '',
     "Cinq étoiles et les gyrophares aux trousses. Série limitée : réservé aux plus recherchés de Leonida."),
    ('vice-nights-username', 'Pseudo Vice Nights', 'username', 'rare', 120, None, '',
     "Ton pseudo en dégradé coucher de soleil, du rose néon au turquoise."),
    ('gyrophare-username', 'Pseudo Gyrophare', 'username', 'epic', 200, None, '',
     "Rouge, bleu, rouge, bleu… Ton pseudo clignote comme une voiture de patrouille de Vice City."),
    ('cash-username', 'Pseudo Liasse de billets', 'username', 'common', 80, None, '',
     "Un pseudo qui sent l'argent facile. Pour celles et ceux qui préparent le prochain coup."),
    ('cocktail-vice-beach', 'Cocktail de Vice Beach', 'consumable', 'rare', 90, None, 'xp_boost',
     "Un cocktail fluo servi sur la plage. Double l'expérience gagnée pendant 24 heures."),
    ('cassette-vice-nights-fm', 'Cassette Vice Nights FM', 'collectible', 'common', 40, None, '',
     "Une compilation synthwave enregistrée à la radio, à écouter vitres baissées."),
    ('carte-postale-leonida', 'Carte postale de Leonida', 'collectible', 'common', 30, None, '',
     "« Bons baisers de Leonida » : palmiers, flamants roses et soleil couchant."),
    ('cles-decapotable', 'Clés de la décapotable', 'collectible', 'epic', 300, 25, '',
     "Les clés d'une décapotable rose bonbon. Série limitée : il n'y en aura pas pour tout le monde."),
]


def forwards(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    Item = apps.get_model('shop', 'Item')

    category, _ = Category.objects.get_or_create(
        name=CATEGORY,
        defaults={'description': "Collection inspirée de GTA 6 et de l'édition spéciale Vice Nights."},
    )
    for css_class, name, kind, rarity, price, stock, effect, description in ITEMS:
        if Item.objects.filter(css_class=css_class).exists():
            continue
        Item.objects.create(
            category=category, name=name, kind=kind, css_class=css_class, rarity=rarity,
            price=price, stock=stock, effect=effect, effect_hours=24, description=description,
        )


def backwards(apps, schema_editor):
    Item = apps.get_model('shop', 'Item')
    Category = apps.get_model('shop', 'Category')
    Item.objects.filter(css_class__in=[row[0] for row in ITEMS], category__name=CATEGORY).delete()
    Category.objects.filter(name=CATEGORY, items__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_paid_themes'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
