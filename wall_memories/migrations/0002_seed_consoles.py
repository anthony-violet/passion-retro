from django.db import migrations
from django.utils.text import slugify

CONSOLES = [
    ('Atari 2600', 'Atari', 1977),
    ('Amstrad CPC', 'Amstrad', 1984),
    ('Commodore 64', 'Commodore', 1982),
    ('Amiga', 'Commodore', 1985),
    ('NES', 'Nintendo', 1985),
    ('Master System', 'Sega', 1986),
    ('Game Boy', 'Nintendo', 1989),
    ('Mega Drive', 'Sega', 1988),
    ('Neo Geo', 'SNK', 1990),
    ('Game Gear', 'Sega', 1990),
    ('Super Nintendo', 'Nintendo', 1990),
    ('Saturn', 'Sega', 1994),
    ('PlayStation', 'Sony', 1994),
    ('Nintendo 64', 'Nintendo', 1996),
    ('Game Boy Color', 'Nintendo', 1998),
    ('Dreamcast', 'Sega', 1998),
    ('PlayStation 2', 'Sony', 2000),
    ('Game Boy Advance', 'Nintendo', 2001),
    ('GameCube', 'Nintendo', 2001),
    ('Xbox', 'Microsoft', 2001),
    ('Nintendo DS', 'Nintendo', 2004),
    ('PSP', 'Sony', 2004),
    ('Xbox 360', 'Microsoft', 2005),
    ('Wii', 'Nintendo', 2006),
    ('PlayStation 3', 'Sony', 2006),
    ('PC', '', None),
    ('Borne d\'arcade', '', None),
]


def seed(apps, schema_editor):
    Console = apps.get_model('wall_memories', 'Console')
    for order, (name, manufacturer, year) in enumerate(CONSOLES, start=1):
        Console.objects.get_or_create(
            name=name,
            defaults={
                'slug': slugify(name),
                'manufacturer': manufacturer,
                'release_year': year,
                'order': order * 10,
            },
        )


def unseed(apps, schema_editor):
    Console = apps.get_model('wall_memories', 'Console')
    Console.objects.filter(name__in=[c[0] for c in CONSOLES], memories__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('wall_memories', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
