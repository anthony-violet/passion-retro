from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from home.models import ChristmasSettings
from panel.decorators import staff_required


class ChristmasSettingsForm(forms.ModelForm):
    class Meta:
        model = ChristmasSettings
        fields = ['mode', 'start_day', 'start_month', 'end_day', 'end_month']
        widgets = {'mode': forms.RadioSelect}


@staff_required
def christmas_view(request):
    # Lecture directe en base (pas le cache) pour éditer la valeur à jour.
    settings_obj, _ = ChristmasSettings.objects.get_or_create(pk=1)
    form = ChristmasSettingsForm(request.POST or None, instance=settings_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Réglages du décor de Noël mis à jour.")
        return redirect('panel_christmas')
    return render(request, 'panel/christmas.html', {
        'form': form,
        'settings_obj': settings_obj,
        'active_today': settings_obj.is_active(timezone.localdate()),
    })
