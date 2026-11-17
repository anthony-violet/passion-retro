from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from posts.models import Post, Category
from posts.notifications import notify_contribution_approved, notify_contribution_rejected


def _redirect_back(request, default='panel_posts'):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(default)


@staff_required
def post_list(request):
    status = request.GET.get('status', 'pending')
    posts = Post.objects.select_related('author', 'category', 'post_parent').order_by('-created')
    if status == 'pending':
        posts = posts.filter(active=False, rejected=False, draft=False, contribution=True)
    elif status == 'active':
        posts = posts.filter(active=True)
    elif status == 'rejected':
        posts = posts.filter(rejected=True)
    return render(request, 'panel/posts/list.html', {'posts': posts, 'status': status})


@staff_required
@require_POST
def post_approve(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.draft:
        messages.error(request, "Ce brouillon n'a pas encore été envoyé par son auteur.")
        return redirect('panel_posts')
    was_online = post.active
    was_rejected = post.rejected
    category_id = request.POST.get('category')
    if post.parent and category_id and Category.objects.filter(pk=category_id).exists():
        post.category_id = int(category_id)
    post.active = True
    post.rejected = False
    post.rejection_reason = ''
    post.save()
    # Publier aussi les chapitres en attente du dossier. Ceux refusés individuellement
    # restent refusés, sauf si tout le dossier avait été refusé (ils l'ont été avec lui).
    chapters_qs = Post.objects.filter(post_parent=post, active=False, draft=False)
    if not was_rejected:
        chapters_qs = chapters_qs.filter(rejected=False)
    chapters = chapters_qs.update(active=True, rejected=False, rejection_reason='')
    notified = None
    if post.contribution and (not was_online or chapters):
        notified = notify_contribution_approved(post, request.user, chapters_count=chapters)
    notice = " Son auteur a été prévenu par message privé." if notified else ""
    if chapters:
        messages.success(request, f"Dossier « {post.title} » publié avec {chapters} chapitre(s).{notice}")
    else:
        messages.success(request, f"Article « {post.title} » publié.{notice}")
    if not post.parent:
        return _redirect_back(request)
    if not post.nav_section:
        messages.warning(request, f"La catégorie « {post.category} » n'est liée à aucune section visible du menu : l'article n'y apparaîtra pas.")
    return _redirect_back(request)


@staff_required
@require_POST
def post_reject(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    post.active = False
    post.rejected = True
    post.rejection_reason = request.POST.get('reason', '').strip()
    post.save()
    # Refuser un dossier refuse aussi tous ses chapitres (sauf les brouillons).
    chapters = 0
    if post.parent:
        chapters = Post.objects.filter(post_parent=post, draft=False).update(
            active=False, rejected=True, rejection_reason=post.rejection_reason,
        )
    notified = notify_contribution_rejected(post, request.user, chapters_count=chapters) if post.contribution else None
    notice = " Son auteur a été prévenu par message privé." if notified else ""
    if chapters:
        messages.success(request, f"Dossier « {post.title} » refusé avec ses {chapters} chapitre(s).{notice}")
    else:
        messages.success(request, f"Article « {post.title} » refusé.{notice}")
    return redirect('panel_posts')


@staff_required
@require_POST
def post_unpublish(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    post.active = False
    post.save()
    messages.success(request, f"Article « {post.title} » retiré du site.")
    return _redirect_back(request)


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
        return redirect('view_post', slug=post.slug)
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
