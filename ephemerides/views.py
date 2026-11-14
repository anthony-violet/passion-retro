from django.conf import settings
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from passion_retro.seo import ephemerides_jsonld
from .models import Ephemeride, ContributedEphemeride


def ephemeride_today(request):
    today = timezone.localdate()
    events = Ephemeride.objects.filter(day=today.day, month=today.month).order_by('-year')
    date_label = today.strftime('%d/%m')
    return render(request, 'ephemerides/today.html', {
        'events': events,
        'today': today,
        'page_title': f"Éphémérides du {date_label} - {settings.SITE_NAME}",
        'page_heading': f"Éphémérides du {date_label}",
        'page_description': (
            f"Découvrez les événements marquants de la culture rétro survenus "
            f"un {date_label} : jeux vidéo, films, séries et musique."
        ),
        'seo_page_jsonld': ephemerides_jsonld(request, events, today),
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
