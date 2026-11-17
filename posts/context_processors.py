from .models import Post


def pending_posts_count(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_staff:
        return {'pending_posts_count': 0}
    count = Post.objects.filter(active=False, rejected=False, draft=False, contribution=True).count()
    return {'pending_posts_count': count}
