from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from panel.decorators import staff_required
from ephemerides.models import Ephemeride, ContributedEphemeride


@staff_required
def ephemeride_list(request):
    month = request.GET.get('month')
    if month:
        events = Ephemeride.objects.filter(month=month).order_by('day', '-year')
    else:
        events = Ephemeride.objects.all().order_by('month', 'day', '-year')
    return render(request, 'panel/ephemerides/list.html', {
        'events': events,
        'selected_month': int(month) if month else None,
        'months': range(1, 13),
    })


@staff_required
def ephemeride_create(request):
    if request.method == 'POST':
        try:
            day = int(request.POST.get('day', 0))
            month = int(request.POST.get('month', 0))
            year = int(request.POST.get('year', 0))
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            category = request.POST.get('category', 'autre')
            if title and 1 <= day <= 31 and 1 <= month <= 12 and year > 0:
                Ephemeride.objects.create(day=day, month=month, year=year, title=title, content=content, category=category)
                messages.success(request, f"Éphéméride « {title} » créée.")
                return redirect('panel_ephemerides')
        except (ValueError, TypeError):
            messages.error(request, "Données invalides.")
    return render(request, 'panel/ephemerides/form.html', {
        'action': 'Créer',
        'categories': Ephemeride.CATEGORY_CHOICES,
    })


@staff_required
def ephemeride_edit(request, event_id):
    event = get_object_or_404(Ephemeride, pk=event_id)
    if request.method == 'POST':
        try:
            event.day = int(request.POST.get('day', event.day))
            event.month = int(request.POST.get('month', event.month))
            event.year = int(request.POST.get('year', event.year))
            event.title = request.POST.get('title', event.title).strip()
            event.content = request.POST.get('content', event.content).strip()
            event.category = request.POST.get('category', event.category)
            event.save()
            messages.success(request, f"Éphéméride « {event.title} » mise à jour.")
            return redirect('panel_ephemerides')
        except (ValueError, TypeError):
            messages.error(request, "Données invalides.")
    return render(request, 'panel/ephemerides/form.html', {
        'action': 'Modifier',
        'event': event,
        'categories': Ephemeride.CATEGORY_CHOICES,
    })


@staff_required
def ephemeride_delete(request, event_id):
    event = get_object_or_404(Ephemeride, pk=event_id)
    if request.method == 'POST':
        title = event.title
        event.delete()
        messages.success(request, f"Éphéméride « {title} » supprimée.")
    return redirect('panel_ephemerides')


@staff_required
def contributed_ephemeride_list(request):
    contributions = ContributedEphemeride.objects.filter(status=ContributedEphemeride.STATUS_PENDING).order_by('-created_at')
    return render(request, 'panel/ephemerides/contributions.html', {
        'contributions': contributions,
    })


@staff_required
def contributed_ephemeride_review(request, contribution_id):
    contribution = get_object_or_404(ContributedEphemeride, pk=contribution_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Créer une nouvelle éphéméride approuvée
            Ephemeride.objects.create(
                day=contribution.day,
                month=contribution.month,
                year=contribution.year,
                title=contribution.title,
                content=contribution.content,
                category=contribution.category
            )
            
            # Mettre à jour la contribution
            contribution.status = ContributedEphemeride.STATUS_APPROVED
            contribution.reviewed_at = timezone.now()
            contribution.reviewed_by = request.user
            contribution.save()
            
            messages.success(request, f"Contribution « {contribution.title} » approuvée et publiée.")
            
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '').strip()
            contribution.status = ContributedEphemeride.STATUS_REJECTED
            contribution.reviewed_at = timezone.now()
            contribution.reviewed_by = request.user
            contribution.rejection_reason = rejection_reason
            contribution.save()
            
            messages.success(request, f"Contribution « {contribution.title} » rejetée.")
            
        return redirect('panel_ephemerides_contributions')
    
    return render(request, 'panel/ephemerides/contribution_review.html', {
        'contribution': contribution,
    })
