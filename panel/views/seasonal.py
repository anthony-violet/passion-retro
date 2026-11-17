from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from home.models import SeasonalEvent
from panel.decorators import staff_required


class SeasonalEventForm(forms.ModelForm):
    class Meta:
        model = SeasonalEvent
        fields = ['mode', 'start_date', 'end_date', 'repeat_yearly']
        widgets = {
            'mode': forms.RadioSelect,
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }


@staff_required
def seasonal_list(request):
    """Liste des décors thématiques, chacun avec son formulaire de période."""
    today = timezone.localdate()
    SeasonalEvent.all_by_key()  # crée les décors manquants
    events = SeasonalEvent.objects.all()

    edited_key = request.POST.get('key') if request.method == 'POST' else None
    rows = []
    for event in events:
        if event.key == edited_key:
            form = SeasonalEventForm(request.POST, instance=event, prefix=event.key)
            if form.is_valid():
                form.save()
                messages.success(request, f"« {event} » mis à jour.")
                return redirect('panel_seasonal')
        else:
            form = SeasonalEventForm(instance=event, prefix=event.key)
        rows.append({'event': event, 'form': form, 'active_today': event.is_active(today)})

    return render(request, 'panel/seasonal.html', {'rows': rows, 'today': today})
