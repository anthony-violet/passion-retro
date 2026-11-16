from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from panel.decorators import staff_required
from wall_memories.models import Console, Memory, MemoryComment
from wall_memories.services import grant_memory_xp, redirect_next


# ── Souvenirs ──────────────────────────────────────────────────────────────

@staff_required
def memory_list(request):
    status = request.GET.get('status', Memory.STATUS_PENDING)
    if status not in dict(Memory.STATUS_CHOICES) and status != 'all':
        status = Memory.STATUS_PENDING
    memories = Memory.objects.select_related('author').prefetch_related('consoles')
    if status != 'all':
        memories = memories.filter(status=status)
    memories = memories.order_by('-created_at')
    page_obj = Paginator(memories, 30).get_page(request.GET.get('page'))
    return render(request, 'panel/wall_memories/memory_list.html', {
        'memories': page_obj,
        'page_obj': page_obj,
        'status': status,
        'statuses': Memory.STATUS_CHOICES,
    })


@staff_required
def memory_review(request, memory_id):
    memory = get_object_or_404(
        Memory.objects.select_related('author').prefetch_related('consoles'), pk=memory_id
    )
    if request.method == 'POST':
        action = request.POST.get('action')
        now = timezone.now()
        if action == 'approve':
            memory.status = Memory.STATUS_PUBLISHED
            memory.published_at = memory.published_at or now
            memory.rejection_reason = ''
            messages.success(request, f"Souvenir « {memory.title} » publié sur le Mur.")
        elif action == 'reject':
            memory.status = Memory.STATUS_REJECTED
            memory.rejection_reason = request.POST.get('rejection_reason', '').strip()
            messages.success(request, f"Souvenir « {memory.title} » refusé.")
        elif action == 'hide':
            memory.status = Memory.STATUS_HIDDEN
            messages.success(request, f"Souvenir « {memory.title} » masqué.")
        else:
            return redirect('panel_memory_review', memory_id=memory.pk)
        memory.reviewed_at = now
        memory.reviewed_by = request.user
        memory.save()
        if memory.status == Memory.STATUS_PUBLISHED:
            grant_memory_xp(memory)
        return redirect('panel_memories')

    return render(request, 'panel/wall_memories/memory_review.html', {'memory': memory})


@staff_required
def memory_delete(request, memory_id):
    memory = get_object_or_404(Memory, pk=memory_id)
    if request.method == 'POST':
        title = memory.title
        memory.delete()
        messages.success(request, f"Souvenir « {title} » supprimé.")
    return redirect('panel_memories')


# ── Commentaires (modération a posteriori) ─────────────────────────────────

@staff_required
def comment_list(request):
    status = request.GET.get('status', 'all')
    comments = MemoryComment.objects.select_related('author', 'memory').order_by('-created_at')
    if status in dict(MemoryComment.STATUS_CHOICES):
        comments = comments.filter(status=status)
    page_obj = Paginator(comments, 40).get_page(request.GET.get('page'))
    return render(request, 'panel/wall_memories/comment_list.html', {
        'comments': page_obj,
        'page_obj': page_obj,
        'status': status,
        'statuses': MemoryComment.STATUS_CHOICES,
    })


@staff_required
def comment_toggle(request, comment_id):
    comment = get_object_or_404(MemoryComment, pk=comment_id)
    if request.method == 'POST':
        comment.status = (
            MemoryComment.STATUS_PUBLISHED
            if comment.status == MemoryComment.STATUS_HIDDEN
            else MemoryComment.STATUS_HIDDEN
        )
        comment.save(update_fields=['status', 'updated_at'])
        comment.memory.refresh_counters()
        messages.success(request, f"Commentaire {comment.get_status_display().lower()}.")
    return redirect_next(request, 'panel_memory_comments')


@staff_required
def comment_delete(request, comment_id):
    comment = get_object_or_404(MemoryComment, pk=comment_id)
    if request.method == 'POST':
        memory = comment.memory
        comment.delete()
        memory.refresh_counters()
        messages.success(request, "Commentaire supprimé.")
    return redirect_next(request, 'panel_memory_comments')


# ── Consoles (liste fermée) ────────────────────────────────────────────────

def _console_from_post(request, console):
    name = request.POST.get('name', '').strip()
    if not name:
        return None, "Le nom est obligatoire."
    duplicate = Console.objects.filter(name__iexact=name)
    if console.pk:
        duplicate = duplicate.exclude(pk=console.pk)
    if duplicate.exists():
        return None, f"La console « {name} » existe déjà."
    slug = slugify(request.POST.get('slug', '').strip() or name)[:110]
    slug_taken = Console.objects.filter(slug=slug)
    if console.pk:
        slug_taken = slug_taken.exclude(pk=console.pk)
    if not slug or slug_taken.exists():
        return None, "Ce slug est déjà utilisé."

    try:
        year = request.POST.get('release_year', '').strip()
        console.release_year = int(year) if year else None
        console.order = int(request.POST.get('order', 0) or 0)
    except ValueError:
        return None, "Année ou ordre invalide."
    console.name = name
    console.slug = slug
    console.manufacturer = request.POST.get('manufacturer', '').strip()
    console.is_active = request.POST.get('is_active') == 'on'
    return console, None


@staff_required
def console_list(request):
    consoles = Console.objects.all()
    return render(request, 'panel/wall_memories/console_list.html', {
        'consoles': [
            (console, console.memories.count()) for console in consoles
        ],
    })


@staff_required
def console_create(request):
    console = Console(is_active=True)
    if request.method == 'POST':
        console, error = _console_from_post(request, console)
        if error:
            messages.error(request, error)
            console = Console(name=request.POST.get('name', ''))
        else:
            console.save()
            messages.success(request, f"Console « {console.name} » ajoutée.")
            return redirect('panel_memory_consoles')
    return render(request, 'panel/wall_memories/console_form.html', {
        'action': 'Ajouter', 'console': console,
    })


@staff_required
def console_edit(request, console_id):
    console = get_object_or_404(Console, pk=console_id)
    if request.method == 'POST':
        updated, error = _console_from_post(request, console)
        if error:
            messages.error(request, error)
            console.refresh_from_db()
        else:
            updated.save()
            messages.success(request, f"Console « {updated.name} » mise à jour.")
            return redirect('panel_memory_consoles')
    return render(request, 'panel/wall_memories/console_form.html', {
        'action': 'Modifier', 'console': console,
    })


@staff_required
def console_delete(request, console_id):
    console = get_object_or_404(Console, pk=console_id)
    if request.method == 'POST':
        if console.memories.exists():
            console.is_active = False
            console.save(update_fields=['is_active'])
            messages.warning(
                request,
                f"« {console.name} » est utilisée par des souvenirs : elle a été désactivée plutôt que supprimée.",
            )
        else:
            name = console.name
            console.delete()
            messages.success(request, f"Console « {name} » supprimée.")
    return redirect('panel_memory_consoles')
