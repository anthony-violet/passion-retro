"""Statistiques internes de fréquentation : visites, provenance, pays.

Indépendant de Google Analytics : rien n'est envoyé à un service extérieur et
l'adresse IP n'est jamais enregistrée (seul le pays qui en est déduit l'est).
"""

import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db.models import F

from .models import Visit, VisitorStats

ACTIVE_WINDOW = timedelta(minutes=5)       # « actuellement sur le site »
VISIT_TIMEOUT = timedelta(minutes=30)      # au-delà, une nouvelle visite commence
VISITOR_SESSION_KEY = 'visitor_id'
VISIT_SESSION_KEY = 'visit_pk'

BOT_MARKERS = (
    'bot', 'crawl', 'spider', 'slurp', 'facebookexternalhit', 'preview',
    'curl', 'wget', 'python-requests', 'httpx', 'headless',
)
# Requêtes techniques qui ne sont pas des pages consultées.
IGNORED_PREFIXES = ('/static/', '/media/', '/api/', '/favicon', '/robots.txt', '/sitemap')


def is_bot(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    return not user_agent or any(marker in user_agent for marker in BOT_MARKERS)


def is_page_view(request):
    """Vraie navigation (page HTML), pas un appel AJAX ni une ressource."""
    if request.method != 'GET' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return False
    path = request.path
    if path.startswith(IGNORED_PREFIXES) or '/api/' in path:
        return False
    accept = request.headers.get('accept', '')
    return not accept or 'text/html' in accept or '*/*' in accept


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# --- Pays ---------------------------------------------------------------------

_reader = None
_reader_loaded = False


def _geoip_reader():
    """Base IP → pays au format MaxMind (.mmdb), si elle est installée.

    Chemin réglable avec ``GEOIP_COUNTRY_DB`` (par ex. la base gratuite
    « IP to Country Lite » de DB-IP). Sans base, le pays reste inconnu.
    """
    global _reader, _reader_loaded
    if not _reader_loaded:
        _reader_loaded = True
        path = getattr(settings, 'GEOIP_COUNTRY_DB', '')
        if path:
            try:
                import maxminddb
                _reader = maxminddb.open_database(str(path))
            except Exception:
                _reader = None
    return _reader


def country_for(request):
    # Derrière Cloudflare, le pays est fourni directement.
    code = request.META.get('HTTP_CF_IPCOUNTRY', '').upper()
    if len(code) == 2 and code.isalpha() and code != 'XX':
        return code
    reader = _geoip_reader()
    ip = client_ip(request)
    if reader is None or not ip:
        return ''
    try:
        record = reader.get(ip) or {}
    except ValueError:
        return ''
    code = ((record.get('country') or {}).get('iso_code') or '').upper()
    return code if len(code) == 2 else ''


# --- Provenance ---------------------------------------------------------------

def referrer_of(request):
    """(URL, domaine) de la page d'où vient le visiteur, si elle est extérieure."""
    referrer = request.META.get('HTTP_REFERER', '').strip()
    if not referrer:
        return '', ''
    host = (urlsplit(referrer).hostname or '').lower()
    own_host = request.get_host().split(':')[0].lower()
    if not host or host.removeprefix('www.') == own_host.removeprefix('www.'):
        return '', ''
    return referrer[:255], host.removeprefix('www.')[:120]


UTM_FIELDS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term')


def utm_of(request):
    """Paramètres UTM de la page d'arrivée (liens de campagne)."""
    return {field: request.GET.get(field, '').strip()[:100] for field in UTM_FIELDS}


# --- Enregistrement -----------------------------------------------------------

def visitor_id(request):
    """Identifiant du visiteur, gardé en session.

    Il survit à la connexion (Django conserve les données de session) : un
    visiteur qui se connecte reste le même visiteur. Sa création compte un
    nouveau visiteur dans le total historique.
    """
    identifier = request.session.get(VISITOR_SESSION_KEY)
    if identifier:
        return identifier
    identifier = uuid.uuid4().hex
    request.session[VISITOR_SESSION_KEY] = identifier
    # Les sessions ouvertes avant ce suivi ont déjà été comptées.
    if not request.session.get('first_visit'):
        request.session['first_visit'] = True
        VisitorStats.objects.get_or_create(pk=1)
        VisitorStats.objects.filter(pk=1).update(total_visitors=F('total_visitors') + 1)
    return identifier


def record(request, now):
    """Note l'activité du visiteur : prolonge sa visite ou en ouvre une nouvelle."""
    identifier = visitor_id(request)
    user = request.user if request.user.is_authenticated else None
    page = is_page_view(request)
    path = request.get_full_path()[:255]

    changes = {'last_seen': now}
    if user is not None:
        changes['user'] = user
    if page:
        changes['current_path'] = path

    visit_pk = request.session.get(VISIT_SESSION_KEY)
    if visit_pk and Visit.objects.filter(
        pk=visit_pk, visitor_id=identifier, last_seen__gte=now - VISIT_TIMEOUT
    ).update(**changes):
        return

    if not page:
        # Une nouvelle visite commence toujours par une vraie page.
        return
    referrer, domain = referrer_of(request)
    visit = Visit.objects.create(
        visitor_id=identifier, user=user, started=now, last_seen=now,
        landing_path=path, current_path=path,
        referrer=referrer, referrer_domain=domain, country=country_for(request),
        **utm_of(request),
    )
    request.session[VISIT_SESSION_KEY] = visit.pk


def active_visits(now):
    return Visit.objects.filter(last_seen__gte=now - ACTIVE_WINDOW)


def active_visitor_count(now):
    return active_visits(now).values('visitor_id').distinct().count()


# --- Affichage ----------------------------------------------------------------

COUNTRY_NAMES = {
    'FR': 'France', 'BE': 'Belgique', 'CH': 'Suisse', 'LU': 'Luxembourg', 'CA': 'Canada',
    'MC': 'Monaco', 'US': 'États-Unis', 'GB': 'Royaume-Uni', 'DE': 'Allemagne',
    'ES': 'Espagne', 'IT': 'Italie', 'PT': 'Portugal', 'NL': 'Pays-Bas', 'IE': 'Irlande',
    'MA': 'Maroc', 'DZ': 'Algérie', 'TN': 'Tunisie', 'SN': 'Sénégal', 'CI': "Côte d'Ivoire",
    'CM': 'Cameroun', 'RE': 'La Réunion', 'GP': 'Guadeloupe', 'MQ': 'Martinique',
    'GF': 'Guyane', 'NC': 'Nouvelle-Calédonie', 'PF': 'Polynésie française',
    'JP': 'Japon', 'CN': 'Chine', 'BR': 'Brésil', 'RU': 'Russie', 'PL': 'Pologne',
    'SE': 'Suède', 'NO': 'Norvège', 'DK': 'Danemark', 'FI': 'Finlande', 'AT': 'Autriche',
}


def country_label(code):
    if not code:
        return '🏳️ Inconnu'
    flag = ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper())
    return f"{flag} {COUNTRY_NAMES.get(code.upper(), code.upper())}"
