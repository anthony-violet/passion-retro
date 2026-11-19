from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from guestbook.models import Guestbook


@staff_required
def guestbook_list(request):
    entries = Guestbook.objects.order_by('-created')
    return render(request, 'panel/guestbook/list.html', {'entries': entries})


@staff_required
@require_POST
def entry_toggle(request, entry_id):
    entry = get_object_or_404(Guestbook, pk=entry_id)
    entry.active = not entry.active
    entry.save()
    messages.success(request, f"Message {'approuvé' if entry.active else 'masqué'}.")
    return redirect('panel_guestbook')


@staff_required
def entry_delete(request, entry_id):
    entry = get_object_or_404(Guestbook, pk=entry_id)
    if request.method == 'POST':
        entry.delete()
        messages.success(request, "Message supprimé.")
    return redirect('panel_guestbook')
