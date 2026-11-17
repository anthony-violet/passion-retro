from django.db import migrations


def fix_child_categories(apps, schema_editor):
    """Aligne la catégorie des articles enfants sur celle de leur dossier."""
    Post = apps.get_model('posts', 'Post')
    for child in Post.objects.filter(post_parent__isnull=False).select_related('post_parent'):
        if child.category_id != child.post_parent.category_id:
            Post.objects.filter(pk=child.pk).update(category_id=child.post_parent.category_id)


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0015_contribution_review'),
    ]

    operations = [
        migrations.RunPython(fix_child_categories, migrations.RunPython.noop),
    ]
