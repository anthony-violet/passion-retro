import re

from django.db import migrations
from django.db.models import F

FORUM_LINK_RE = re.compile(r"^/?forum/\d+/(\d+)/?$")


def backfill(apps, schema_editor):
    Post = apps.get_model('posts', 'Post')
    Topic = apps.get_model('forum', 'Topic')

    # Les articles déjà en ligne gardent leur date de création comme date de publication.
    Post.objects.filter(active=True, published_at__isnull=True).update(published_at=F('created'))

    # forum_link (texte) → topic (relation)
    for post in Post.objects.filter(topic__isnull=True).exclude(forum_link__isnull=True).exclude(forum_link=''):
        match = FORUM_LINK_RE.match(post.forum_link.strip())
        if not match:
            continue
        topic_id = int(match.group(1))
        if Topic.objects.filter(pk=topic_id).exists():
            Post.objects.filter(pk=post.pk).update(topic_id=topic_id)


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0018_news_fields'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
