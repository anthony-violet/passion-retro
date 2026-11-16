import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse

from passion_retro.seo import plain_text

from .models import Post, TopicSubscription


logger = logging.getLogger(__name__)


def update_subscription(user, topic, subscribe):
    subscription, created = TopicSubscription.objects.get_or_create(
        user=user,
        topic=topic,
        defaults={'active': subscribe},
    )
    if not created and subscription.active != subscribe:
        subscription.active = subscribe
        subscription.save(update_fields=['active', 'updated'])
    return subscription


def notify_topic_subscribers(post):
    if not post.active:
        return

    topic = post.topic
    forum = topic.forum
    subscriptions = TopicSubscription.objects.filter(
        topic=topic,
        active=True,
        user__active=True,
        user__is_active=True,
    ).exclude(
        user=post.author
    ).exclude(
        user__email=''
    ).select_related('user')

    if not subscriptions:
        return

    base_url = settings.SITE_URL.rstrip('/')
    topic_path = reverse('post_list', args=[topic.forum_id, topic.id])
    post_position = Post.objects.filter(
        topic=topic,
        active=True,
        created__lte=post.created,
    ).count()
    page = max(1, (post_position + 19) // 20)
    post_url = f"{base_url}{topic_path}?page={page}#post-{post.id}"
    subject = f"[{settings.SITE_NAME}] Nouvelle réponse : {topic.title}"

    messages = []
    for subscription in subscriptions:
        unsubscribe_url = (
            f"{base_url}"
            f"{reverse('unsubscribe_topic', args=[subscription.token])}"
        )
        context = {
            'recipient': subscription.user,
            'post': post,
            'topic': topic,
            'forum': forum,
            'author': post.author,
            'excerpt': plain_text(post.content, 300),
            'post_url': post_url,
            'unsubscribe_url': unsubscribe_url,
            'site_name': settings.SITE_NAME,
        }
        text_body = render_to_string('emails/topic_reply.txt', context)
        html_body = render_to_string('emails/topic_reply.html', context)

        message = EmailMultiAlternatives(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [subscription.user.email],
        )
        message.attach_alternative(html_body, 'text/html')
        message.extra_headers = {
            'List-Unsubscribe': f'<{unsubscribe_url}>',
        }
        messages.append(message)

    if not messages:
        return

    connection = get_connection()
    try:
        connection.send_messages(messages)
    except Exception:
        logger.exception(
            "Échec de l'envoi des notifications du sujet %s",
            topic.id,
        )
