"""Actus : publication, sujet du forum associé et réactions."""
import logging

from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce, Greatest
from django.urls import reverse
from django.utils import timezone

from forum.models import Forum, Topic, Post as ForumPost

logger = logging.getLogger(__name__)

NEWS_FORUM_NAME = 'Actus du site'
TOPIC_TITLE_MAX = Topic._meta.get_field('title').max_length
XP_NEWS_PUBLISHED = 20
XP_REACTION = 10
XP_FIRST_REACTION_BONUS = 5
HOT_REACTIONS = 10  # à partir de ce nombre, la discussion est mise en avant


def with_discussion(queryset):
    """Annoter des actus avec le nombre de réactions et la dernière activité du forum.

    Le premier message du sujet est la recopie de l'actu : il n'est pas compté.
    """
    active_posts = Q(topic__posts__active=True)
    return queryset.annotate(
        reactions=Greatest(Count('topic__posts', filter=active_posts) - 1, 0),
        last_activity=Max('topic__posts__created', filter=active_posts),
    )


def news_queryset():
    """Actus en ligne, annotées pour l'affichage, de la plus récente à la plus ancienne."""
    from posts.models import Post

    qs = (
        Post.objects.filter(type='news', active=True, post_parent__isnull=True)
        .select_related('author', 'category', 'topic')
        .prefetch_related('author__levels')
        .annotate(pub_date=Coalesce('published_at', 'created'))
    )
    return with_discussion(qs).order_by('-pub_date', '-pk')


def latest_reactions(post, limit=3):
    """Dernières réactions du sujet lié (hors message d'ouverture), dans l'ordre chronologique."""
    if not post or not post.topic_id:
        return []
    posts = ForumPost.objects.filter(topic_id=post.topic_id, active=True)
    opening = posts.order_by('created', 'pk').values_list('pk', flat=True).first()
    latest = (
        posts.exclude(pk=opening).select_related('author')
        .prefetch_related('author__levels').order_by('-created', '-pk')[:limit]
    )
    return list(reversed(latest))


def _topic_title(title):
    if len(title) <= TOPIC_TITLE_MAX:
        return title
    return title[: TOPIC_TITLE_MAX - 1].rstrip() + '…'


def _opening_message(post):
    parts = []
    if post.image:
        parts.append(f'[img alt={post.title}]{post.image.url}[/img]')
    parts.append(post.summary)
    if post.forum_prompt:
        parts.append(f'[b]{post.forum_prompt}[/b]')
    parts.append(f"[url={reverse('view_post', args=[post.slug])}]Lire l'actu complète sur le site[/url]")
    return '\n\n'.join(parts)


def publish_news(post):
    """À appeler quand une actu passe en ligne. Sans effet si déjà fait.

    Fixe la date de publication et crée le sujet de discussion sur le forum.
    """
    if post.type != 'news' or not post.active or post.post_parent_id:
        return
    from users.leveling import GOLD_BIG_ACTION, GOLD_SMALL_ACTION, grant_experience

    updates = {}
    if post.published_at is None:
        updates['published_at'] = timezone.now()

    created_topic = False
    if post.topic_id is None:
        forum = Forum.objects.filter(name=NEWS_FORUM_NAME).first()
        if forum is None:
            logger.warning("Forum « %s » introuvable : pas de sujet pour l'actu %s.", NEWS_FORUM_NAME, post.pk)
        else:
            with transaction.atomic():
                topic = Topic.objects.create(title=_topic_title(post.title), forum=forum, author=post.author)
                ForumPost.objects.create(topic=topic, author=post.author, content=_opening_message(post))
            updates['topic'] = topic
            updates['forum_link'] = f'forum/{forum.id}/{topic.id}/'
            created_topic = True

    if updates:
        for field, value in updates.items():
            setattr(post, field, value)
        type(post).objects.filter(pk=post.pk).update(**updates)
    if created_topic:
        grant_experience(post.author, XP_NEWS_PUBLISHED, gold=GOLD_BIG_ACTION)


def react_to_news(post, user, content, subscribe):
    """Publier une réaction dans le sujet du forum de l'actu.

    Retourne (message_forum, xp_gagnée).
    """
    from forum.notifications import notify_topic_subscribers, update_subscription
    from users.leveling import GOLD_BIG_ACTION, GOLD_SMALL_ACTION, grant_experience

    topic = post.topic
    first_reaction = not ForumPost.objects.filter(topic=topic, author=user).exists()
    forum_post = ForumPost.objects.create(topic=topic, author=user, content=content)
    Topic.objects.filter(pk=topic.pk).update(updated=timezone.now())
    update_subscription(user, topic, subscribe)
    notify_topic_subscribers(forum_post)
    xp = XP_REACTION + (XP_FIRST_REACTION_BONUS if first_reaction else 0)
    grant_experience(user, xp, gold=GOLD_SMALL_ACTION)
    return forum_post, xp


def topic_url(topic):
    return reverse('post_list', args=[topic.forum_id, topic.id])
