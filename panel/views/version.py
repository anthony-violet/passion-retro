from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from version.forms import HistoryVersionForm
from version.models import HistoryVersion


@staff_required
def version_list(request):
    versions = HistoryVersion.objects.all().order_by('-created_at')
    return render(request, 'panel/version/list.html', {'versions': versions})


@staff_required
def version_create(request):
    form = HistoryVersionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        version = form.save()
        messages.success(request, f"Version « {version.num_version} – {version.name} » créée.")
        return redirect('panel_version')
    return render(request, 'panel/version/form.html', {'action': 'Créer', 'form': form})


@staff_required
def version_edit(request, version_id):
    version = get_object_or_404(HistoryVersion, pk=version_id)
    form = HistoryVersionForm(request.POST or None, request.FILES or None, instance=version)
    if request.method == 'POST' and form.is_valid():
        version = form.save()
        messages.success(request, f"Version « {version.num_version} » mise à jour.")
        return redirect('panel_version')
    return render(request, 'panel/version/form.html', {'action': 'Modifier', 'version': version, 'form': form})


@staff_required
def version_delete(request, version_id):
    version = get_object_or_404(HistoryVersion, pk=version_id)
    if request.method == 'POST':
        label = f"{version.num_version} – {version.name}"
        version.delete()
        messages.success(request, f"Version « {label} » supprimée.")
    return redirect('panel_version')
