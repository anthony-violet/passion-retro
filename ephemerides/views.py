from django.shortcuts import render
from django.utils import timezone
from .models import Ephemeride


def ephemeride_today(request):
    today = timezone.localdate()
    events = Ephemeride.objects.filter(day=today.day, month=today.month).order_by('-year')
    return render(request, 'ephemerides/today.html', {
        'events': events,
        'today': today,
    })
