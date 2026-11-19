from datetime import timedelta

from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from panel.decorators import staff_required
from users import visits
from users.models import Visit, VisitorStats

PERIODS = {1: "24 dernières heures", 7: "7 derniers jours", 30: "30 derniers jours", 365: "12 derniers mois"}


def _latest_per(queryset, key):
    """Garde la visite la plus récente pour chaque valeur de ``key``."""
    seen, rows = set(), []
    for visit in queryset.order_by('-last_seen'):
        value = getattr(visit, key)
        if value not in seen:
            seen.add(value)
            rows.append(visit)
    return rows


def _with_share(rows, total):
    for row in rows:
        row['share'] = round(100 * row['count'] / total) if total else 0
    return rows


@staff_required
def stats_overview(request):
    now = timezone.now()
    try:
        days = int(request.GET.get('periode', 30))
    except ValueError:
        days = 30
    if days not in PERIODS:
        days = 30
    since = now - timedelta(days=days)

    active = visits.active_visits(now).select_related('user')
    online_visitors = _latest_per(active, 'visitor_id')
    online_members = _latest_per(active.filter(user__isnull=False), 'user_id')
    for visit in online_visitors + online_members:
        visit.country_label = visits.country_label(visit.country)

    period_visits = Visit.objects.filter(started__gte=since)
    unique_visitors = period_visits.values('visitor_id').distinct().count()

    countries = list(period_visits.values('country')
                     .annotate(count=Count('visitor_id', distinct=True)).order_by('-count'))
    for row in countries:
        row['label'] = visits.country_label(row['country'])

    sources = list(period_visits.values('referrer_domain')
                   .annotate(count=Count('id')).order_by('-count')[:20])
    landing = list(period_visits.values('landing_path')
                   .annotate(count=Count('id')).order_by('-count')[:10])

    def unique_since(delta):
        return (Visit.objects.filter(last_seen__gte=now - delta)
                .values('visitor_id').distinct().count())

    campaigns = list(period_visits.exclude(utm_campaign='', utm_source='')
                     .values('utm_campaign', 'utm_source', 'utm_medium')
                     .annotate(count=Count('id'), visitors=Count('visitor_id', distinct=True))
                     .order_by('-count')[:20])

    stats = VisitorStats.objects.filter(pk=1).first()
    return render(request, 'panel/stats/overview.html', {
        'online_visitors': online_visitors,
        'online_members': online_members,
        'unique_today': unique_since(timedelta(days=1)),
        'unique_week': unique_since(timedelta(days=7)),
        'unique_month': unique_since(timedelta(days=30)),
        'total_visitors': stats.total_visitors if stats else 0,
        'period_days': days,
        'period_label': PERIODS[days],
        'periods': PERIODS.items(),
        'period_visits': period_visits.count(),
        'unique_visitors': unique_visitors,
        'countries': _with_share(countries, unique_visitors),
        'sources': _with_share(sources, period_visits.count()),
        'landing': landing,
        'campaigns': campaigns,
        'geoip_enabled': visits._geoip_reader() is not None,
    })


# --- Gestionnaire de liens UTM ------------------------------------------------

from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify

from users.models import UtmLink

UTM_SUGGESTIONS = {
    'source': ['facebook', 'instagram', 'discord', 'twitter', 'reddit', 'youtube', 'newsletter', 'forum'],
    'medium': ['social', 'email', 'post', 'story', 'banniere', 'video', 'partenaire'],
}


def _site_url(request):
    return (getattr(settings, 'SITE_URL', '') or request.build_absolute_uri('/')).rstrip('/')


def utm_url(request, link):
    destination = link.destination if link.destination.startswith('/') else '/' + link.destination
    separator = '&' if '?' in destination else '?'
    return f"{_site_url(request)}{destination}{separator}{urlencode(link.query_params())}"


def _utm_value(raw):
    """Valeurs UTM homogènes : minuscules, sans accents ni espaces."""
    return slugify(raw or '')[:100]


@staff_required
def utm_list(request):
    since = timezone.now() - timedelta(days=30)
    links = list(UtmLink.objects.select_related('created_by'))
    for link in links:
        visits_qs = link.visits()
        link.url = utm_url(request, link)
        link.nb_visits = visits_qs.count()
        link.nb_visits_month = visits_qs.filter(started__gte=since).count()
        link.nb_visitors = visits_qs.values('visitor_id').distinct().count()
        link.nb_members = visits_qs.filter(user__isnull=False).values('user_id').distinct().count()
    return render(request, 'panel/stats/utm_list.html', {'links': links})


def _utm_form(request, link, action):
    if request.method == 'POST':
        link.name = request.POST.get('name', '').strip()[:120]
        destination = request.POST.get('destination', '').strip() or '/'
        link.destination = (destination if destination.startswith('/') else '/' + destination)[:255]
        for field in ('source', 'medium', 'campaign', 'content', 'term'):
            setattr(link, field, _utm_value(request.POST.get(field)))
        if not (link.name and link.source and link.medium and link.campaign):
            messages.error(request, "Le nom, la source, le support et la campagne sont obligatoires.")
        elif destination.startswith(('http://', 'https://', '//')):
            messages.error(request, "La destination doit être une page du site (ex. /games/mystere).")
        else:
            if link.created_by_id is None:
                link.created_by = request.user
            link.save()
            messages.success(request, f"Lien « {link.name} » enregistré.")
            return redirect('panel_utm_list')
    return render(request, 'panel/stats/utm_form.html', {
        'link': link, 'action': action, 'suggestions': UTM_SUGGESTIONS,
        'site_url': _site_url(request),
    })


@staff_required
def utm_create(request):
    return _utm_form(request, UtmLink(), 'Créer')


@staff_required
def utm_edit(request, link_id):
    return _utm_form(request, get_object_or_404(UtmLink, pk=link_id), 'Modifier')


@staff_required
def utm_delete(request, link_id):
    link = get_object_or_404(UtmLink, pk=link_id)
    if request.method == 'POST':
        link.delete()
        messages.success(request, f"Lien « {link.name} » supprimé (les visites restent comptées).")
    return redirect('panel_utm_list')
