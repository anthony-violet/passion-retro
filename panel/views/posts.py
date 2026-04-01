from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from posts.models import Post, Category


@staff_required
def post_list(request):
    status = request.GET.get('status', 'pending')
    if status == 'pending':
        posts = Post.objects.filter(active=False, contribution=True).select_related('author', 'category').order_by('-created')
    elif status == 'active':
        posts = Post.objects.filter(active=True).select_related('author', 'category').order_by('-created')
    else:
        posts = Post.objects.select_related('author', 'category').order_by('-created')
    return render(request, 'panel/posts/list.html', {'posts': posts, 'status': status})


@staff_required
def post_approve(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    post.active = True
    post.save()
    # Approuver aussi les enfants
    Post.objects.filter(post_parent=post).update(active=True)
    messages.success(request, f"Article « {post.title} » approuvé.")
    return redirect('panel_posts')


@staff_required
def post_reject(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    post.active = False
    post.save()
    messages.success(request, f"Article « {post.title} » rejeté.")
    return redirect('panel_posts')


@staff_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
        title = post.title
        post.delete()
        messages.success(request, f"Article « {title} » supprimé.")
    return redirect('panel_posts')


@staff_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    categories = Category.objects.all()
    if request.method == 'POST':
        post.title = request.POST.get('title', post.title)
        post.content = request.POST.get('content', post.content)
        post.category_id = request.POST.get('category', post.category_id)
        post.active = 'active' in request.POST
        post.save()
        messages.success(request, "Article mis à jour.")
        return redirect('panel_posts')
    return render(request, 'panel/posts/edit.html', {'post': post, 'categories': categories})


@staff_required
def category_list(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            Category.objects.create(name=name)
            messages.success(request, "Catégorie créée.")
        return redirect('panel_post_categories')
    return render(request, 'panel/posts/categories.html', {'categories': categories})


@staff_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Catégorie supprimée.")
    return redirect('panel_post_categories')
