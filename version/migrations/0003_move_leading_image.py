import re

from django.db import migrations

# Une version dont le texte commence par [img]/media/…[/img] : l'image devient
# la capture d'écran de la version et sort du texte.
LEADING_IMAGE = re.compile(r'^\s*\[img(?: alt=[^\]]*)?\]/media/([^\[\]\s]+)\[/img\]\s*', re.IGNORECASE)


def split_leading_image(content):
    """Retourne (chemin média de l'image ou None, contenu sans l'image)."""
    match = LEADING_IMAGE.match(content or '')
    if not match:
        return None, content
    return match.group(1), content[match.end():]


def move_images(apps, schema_editor):
    HistoryVersion = apps.get_model('version', 'HistoryVersion')
    for version in HistoryVersion.objects.all():
        if version.image:
            continue
        path, content = split_leading_image(version.content)
        if path:
            version.image = path
            version.content = content
            version.save(update_fields=['image', 'content'])


def restore_images(apps, schema_editor):
    HistoryVersion = apps.get_model('version', 'HistoryVersion')
    for version in HistoryVersion.objects.exclude(image='').exclude(image__isnull=True):
        version.content = f'[img]/media/{version.image}[/img]\n{version.content}'
        version.image = None
        version.save(update_fields=['image', 'content'])


class Migration(migrations.Migration):

    dependencies = [
        ('version', '0002_version_image'),
    ]

    operations = [
        migrations.RunPython(move_images, restore_images),
    ]
