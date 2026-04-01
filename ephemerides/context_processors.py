from django.utils import timezone
from .models import Ephemeride


def ephemerides_today(request):
    today = timezone.localdate()
    events = Ephemeride.objects.filter(day=today.day, month=today.month).order_by('-year')
    return {
        'ephemerides_today': events,
    }
