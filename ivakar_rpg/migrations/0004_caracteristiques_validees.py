"""Crée les sept caractéristiques validées (règles d'Ivakar, IV), sans toucher à celles qui existent."""
from django.db import migrations

CHARACTERISTICS = [
    ('force', "Force", "Puissance physique brute et effort musculaire."),
    ('constitution', "Constitution", "Vitalité, résistance corporelle, endurance physique et récupération."),
    ('dexterite', "Dextérité", "Fluidité du mouvement, équilibre, précision et coordination."),
    ('perception', "Perception", "Détection et première interprétation des informations de l'environnement."),
    ('intelligence', "Intelligence", "Compréhension, raisonnement, apprentissage, planification et traitement "
                                     "logique de l'information."),
    ('mental', "Mental", "Résistance psychologique, détermination et discipline face à la pression."),
    ('charisme', "Charisme", "Effet produit sur autrui : convaincre, impressionner, intimider, inspirer ou captiver."),
]


def create_characteristics(apps, schema_editor):
    Characteristic = apps.get_model('ivakar_rpg', 'Characteristic')
    for order, (code, name, description) in enumerate(CHARACTERISTICS, start=1):
        Characteristic.objects.get_or_create(code=code, defaults={'name': name, 'description': description,
                                                                  'order': order})


class Migration(migrations.Migration):

    dependencies = [
        ('ivakar_rpg', '0003_illustrations_et_carte'),
    ]

    operations = [
        migrations.RunPython(create_characteristics, migrations.RunPython.noop),
    ]
