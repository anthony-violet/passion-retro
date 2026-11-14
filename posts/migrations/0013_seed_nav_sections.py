from django.db import migrations

SECTIONS = [
    {"label": "Jeux", "type_key": "games", "order": 1},
    {"label": "Films & Series", "type_key": "movies", "order": 2},
    {"label": "Musique", "type_key": "music", "order": 3},
    {"label": "Technologies", "type_key": "tech", "order": 4},
]


def create_nav_sections(apps, schema_editor):
    NavSection = apps.get_model("posts", "NavSection")
    for data in SECTIONS:
        NavSection.objects.get_or_create(
            type_key=data["type_key"],
            defaults={"label": data["label"], "order": data["order"]},
        )


def delete_nav_sections(apps, schema_editor):
    NavSection = apps.get_model("posts", "NavSection")
    NavSection.objects.filter(type_key__in=[s["type_key"] for s in SECTIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0012_navsection"),
    ]

    operations = [
        migrations.RunPython(create_nav_sections, delete_nav_sections),
    ]
