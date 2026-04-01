from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Ephemeride, ContributedEphemeride


def ephemeride_today(request):
    today = timezone.localdate()
    events = Ephemeride.objects.filter(day=today.day, month=today.month).order_by('-year')
    return render(request, 'ephemerides/today.html', {
        'events': events,
        'today': today,
    })


@login_required
def contribute_ephemeride(request):
    if request.method == 'POST':
        try:
            day = int(request.POST.get('day', 0))
            month = int(request.POST.get('month', 0))
            year = int(request.POST.get('year', 0))
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            category = request.POST.get('category', 'autre')
            
            if title and 1 <= day <= 31 and 1 <= month <= 12 and year > 0:
                ContributedEphemeride.objects.create(
                    day=day,
                    month=month,
                    year=year,
                    title=title,
                    content=content,
                    category=category,
                    user=request.user
                )
                messages.success(request, "Votre contribution a été soumise avec succès ! Elle sera examinée par l'équipe.")
                return redirect('ephemerides_today')
            else:
                messages.error(request, "Veuillez remplir tous les champs correctement.")
        except (ValueError, TypeError):
            messages.error(request, "Données invalides. Veuillez vérifier les informations saisies.")
    
    return render(request, 'ephemerides/contribute.html', {
        'categories': ContributedEphemeride.CATEGORY_CHOICES,
    })
