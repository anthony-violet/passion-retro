from django.shortcuts import render, redirect
from django.contrib import messages
from panel.decorators import staff_required
from maintenance.models import Informations


@staff_required
def maintenance_view(request):
    info, _ = Informations.objects.get_or_create(pk=1, defaults={'name': 'Maintenance en cours', 'content': '', 'is_active': False})
    if request.method == 'POST':
        info.name = request.POST.get('name', info.name)
        info.content = request.POST.get('content', info.content)
        info.is_active = 'is_active' in request.POST
        info.save()
        messages.success(request, "Paramètres de maintenance mis à jour.")
        return redirect('panel_maintenance')
    return render(request, 'panel/maintenance.html', {'info': info})
