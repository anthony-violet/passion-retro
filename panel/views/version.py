from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from version.models import HistoryVersion


@staff_required
def version_list(request):
    versions = HistoryVersion.objects.all().order_by('-created_at')
    return render(request, 'panel/version/list.html', {'versions': versions})


@staff_required
def version_create(request):
    if request.method == 'POST':
        num_version = request.POST.get('num_version', '').strip()
        name = request.POST.get('name', '').strip()
        content = request.POST.get('content', '').strip()
        if num_version and name:
            HistoryVersion.objects.create(num_version=num_version, name=name, content=content)
            messages.success(request, f"Version « {num_version} – {name} » créée.")
            return redirect('panel_version')
    return render(request, 'panel/version/form.html', {'action': 'Créer'})


@staff_required
def version_edit(request, version_id):
    version = get_object_or_404(HistoryVersion, pk=version_id)
    if request.method == 'POST':
        version.num_version = request.POST.get('num_version', version.num_version).strip()
        version.name = request.POST.get('name', version.name).strip()
        version.content = request.POST.get('content', version.content).strip()
        version.save()
        messages.success(request, f"Version « {version.num_version} » mise à jour.")
        return redirect('panel_version')
    return render(request, 'panel/version/form.html', {'action': 'Modifier', 'version': version})


@staff_required
def version_delete(request, version_id):
    version = get_object_or_404(HistoryVersion, pk=version_id)
    if request.method == 'POST':
        label = f"{version.num_version} – {version.name}"
        version.delete()
        messages.success(request, f"Version « {label} » supprimée.")
    return redirect('panel_version')
