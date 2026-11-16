from django.shortcuts import render
from panel.decorators import staff_required
from users.models import User
from forum.models import Topic, Post as ForumPost, Category as ForumCategory, Forum
from posts.models import Post, Category as PostCategory
from quiz.models import Quiz
from guestbook.models import Guestbook
from shop.models import Item
from ephemerides.models import ContributedEphemeride
from wall_memories.models import Memory


@staff_required
def dashboard(request):
    ctx = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(active=True).count(),
        'inactive_users': User.objects.filter(active=False).count(),
        'new_users': User.objects.order_by('-date_joined')[:5],

        'total_posts': Post.objects.count(),
        'pending_posts': Post.objects.filter(active=False, contribution=True).count(),

        'total_forum_topics': Topic.objects.count(),
        'total_forum_posts': ForumPost.objects.count(),

        'total_quizzes': Quiz.objects.count(),
        'pending_quizzes': Quiz.objects.filter(is_active=False).count(),

        'total_guestbook': Guestbook.objects.count(),
        'pending_guestbook': Guestbook.objects.filter(active=False).count(),

        'pending_ephemerides': ContributedEphemeride.objects.filter(
            status=ContributedEphemeride.STATUS_PENDING
        ).count(),

        'total_memories': Memory.objects.filter(status=Memory.STATUS_PUBLISHED).count(),
        'pending_memories': Memory.objects.filter(status=Memory.STATUS_PENDING).count(),

        'total_items': Item.objects.count(),
    }
    return render(request, 'panel/dashboard.html', ctx)
