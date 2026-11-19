from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from forum.models import Category, Forum, Topic, Post


@staff_required
def forum_overview(request):
    categories = Category.objects.prefetch_related('forum_set').order_by('name')
    return render(request, 'panel/forum/overview.html', {'categories': categories})


@staff_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            Category.objects.create(name=name, description=description)
            messages.success(request, "Catégorie créée.")
        return redirect('panel_forum')
    return render(request, 'panel/forum/category_form.html', {'action': 'Créer'})


@staff_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name', category.name).strip()
        category.description = request.POST.get('description', '').strip()
        category.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect('panel_forum')
    return render(request, 'panel/forum/category_form.html', {'action': 'Modifier', 'category': category})


@staff_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Catégorie supprimée.")
    return redirect('panel_forum')


@staff_required
def forum_create(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        if name and category_id:
            Forum.objects.create(
                name=name,
                description=description,
                category_id=category_id,
                author=request.user,
            )
            messages.success(request, "Forum créé.")
        return redirect('panel_forum')
    return render(request, 'panel/forum/forum_form.html', {'action': 'Créer', 'categories': categories})


@staff_required
def forum_edit(request, forum_id):
    forum = get_object_or_404(Forum, pk=forum_id)
    categories = Category.objects.all()
    if request.method == 'POST':
        forum.name = request.POST.get('name', forum.name).strip()
        forum.description = request.POST.get('description', '').strip()
        forum.category_id = request.POST.get('category', forum.category_id)
        forum.save()
        messages.success(request, "Forum mis à jour.")
        return redirect('panel_forum')
    return render(request, 'panel/forum/forum_form.html', {'action': 'Modifier', 'forum': forum, 'categories': categories})


@staff_required
def forum_delete(request, forum_id):
    forum = get_object_or_404(Forum, pk=forum_id)
    if request.method == 'POST':
        forum.delete()
        messages.success(request, "Forum supprimé.")
    return redirect('panel_forum')


@staff_required
def topic_list(request):
    topics = Topic.objects.select_related('forum', 'author').order_by('-created')[:100]
    return render(request, 'panel/forum/topics.html', {'topics': topics})


@staff_required
@require_POST
def topic_toggle_state(request, topic_id):
    topic = get_object_or_404(Topic, pk=topic_id)
    topic.state = 'closed' if topic.state == 'open' else 'open'
    topic.save()
    messages.success(request, f"Sujet {'fermé' if topic.state == 'closed' else 'ouvert'}.")
    return redirect('panel_forum_topics')


@staff_required
def post_list(request):
    posts = Post.objects.select_related('topic', 'author').order_by('-created')[:100]
    return render(request, 'panel/forum/posts.html', {'posts': posts})


@staff_required
@require_POST
def post_toggle_active(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    post.active = not post.active
    post.save()
    messages.success(request, f"Message {'activé' if post.active else 'désactivé'}.")
    return redirect('panel_forum_posts')


@staff_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
        post.delete()
        messages.success(request, "Message supprimé.")
    return redirect('panel_forum_posts')
