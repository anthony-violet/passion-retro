from datetime import date

from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.formats import date_format

from home.models import SeasonalEvent
from panel.decorators import staff_required
from django.contrib.staticfiles import finders
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from passion_retro.seasonal import PREVIEW_SESSION_KEY, SPECIAL_EDITIONS
from passion_retro.theme_config import THEME_CONFIGS

# Présentation de chaque décor dans le panel
EVENT_INFO = {
    SeasonalEvent.CHRISTMAS: {
        "icon": "🎄",
        "kind": "Décor",
        "description": "Neige, guirlande, bonnet et sapins, posés par-dessus le thème de chaque visiteur.",
    },
    SeasonalEvent.DOOMSDAY: {
        "icon": "🛡️",
        "kind": "Édition spéciale",
        "description": "Thème Avengers : Doomsday imposé à tout le site, avec bannière et encart d'accueil.",
    },
    SeasonalEvent.VICECITY: {
        "icon": "🌴",
        "kind": "Édition spéciale",
        "description": "Thème Vice Nights (sortie de GTA VI) imposé à tout le site, avec bannière et encart d'accueil.",
    },
}
EDITION_PRIORITY = list(SPECIAL_EDITIONS)


class SeasonalEventForm(forms.ModelForm):
    class Meta:
        model = SeasonalEvent
        fields = ['mode', 'start_date', 'end_date', 'repeat_yearly']
        widgets = {
            'mode': forms.RadioSelect,
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }
        labels = {'repeat_yearly': "Revient chaque année"}

    def __init__(self, *args, today=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Période annuelle : l'année enregistrée ne compte pas (souvent 2000).
        # On affiche les dates de la période en cours ou à venir, plus parlantes.
        event = self.instance
        if not self.is_bound and event.repeat_yearly and event.start_date and event.end_date and today:
            start, end = _cycle(event, today)
            self.initial['start_date'] = start
            self.initial['end_date'] = end


def _short(day: date, with_year: bool = True) -> str:
    return date_format(day, "j F Y" if with_year else "j F")


def _in_year(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:  # 29 février
        return date(year, 3, 1)


def _cycle(event, today: date):
    """Période annuelle en cours, ou la prochaine, avec de vraies années."""
    for year in (today.year - 1, today.year, today.year + 1):
        start = _in_year(event.start_date, year)
        end = _in_year(event.end_date, year)
        if end < start:  # passe le 31 décembre
            end = _in_year(event.end_date, year + 1)
        if end >= today:
            return start, end
    return start, end


def _period_label(event):
    if not event.start_date or not event.end_date:
        return "Aucune période"
    if event.repeat_yearly:
        return f"Du {_short(event.start_date, False)} au {_short(event.end_date, False)}, chaque année"
    return f"Du {_short(event.start_date)} au {_short(event.end_date)}"


def _next_start(event, today: date):
    """Prochain début de période."""
    if not event.start_date:
        return None
    if not event.repeat_yearly:
        return event.start_date
    start, _end = _cycle(event, today)
    return start if start > today else _in_year(event.start_date, start.year + 1)


def _days(n: int) -> str:
    return "demain" if n == 1 else f"dans {n} jours"


def _status(event, today: date, shown_edition):
    """(libellé, ton du badge, précision) pour l'état du décor aujourd'hui."""
    if event.mode == SeasonalEvent.MODE_OFF:
        return "Désactivé", "muted", "Ne s'affiche jamais, quelles que soient les dates."
    active = event.is_active(today)
    if active and event.key in SPECIAL_EDITIONS and shown_edition and shown_edition.key != event.key:
        return "En attente", "warning", f"Période en cours, mais « {shown_edition} » est prioritaire."
    if event.mode == SeasonalEvent.MODE_ON:
        return "Affiché", "success", "Toujours affiché, sans tenir compte des dates."
    if active:
        return "Affiché", "success", f"Jusqu'au {_short(_period_end(event, today))} inclus."
    start = _next_start(event, today)
    if start and start > today:
        return "Programmé", "info", f"Commence le {_short(start)} ({_days((start - today).days)})."
    return "Terminé", "muted", "La période est passée : choisis de nouvelles dates pour le reprogrammer."


def _period_end(event, today: date) -> date:
    """Date de fin de la période en cours."""
    return _cycle(event, today)[1] if event.repeat_yearly else event.end_date


def preview_choices():
    """Thèmes proposés en aperçu : (éditions spéciales, thèmes ordinaires), chacun (clé, nom, icône)."""
    editions, themes = [], []
    for key, config in THEME_CONFIGS.items():
        if not finders.find(f"themes/{key}/theme.css"):
            continue
        edition = next((k for k, e in SPECIAL_EDITIONS.items() if e["theme"] == key), None)
        if edition:
            editions.append((key, config["name"].replace("Édition spéciale ", ""), SPECIAL_EDITIONS[edition]["icon"]))
        else:
            themes.append((key, config["name"], ""))
    return editions, themes


@staff_required
@require_POST
def seasonal_preview(request):
    """Active ou arrête l'aperçu d'un thème / du décor de Noël, pour ce membre du staff seulement."""
    theme = request.POST.get("theme", "")
    christmas = request.POST.get("christmas") == "1"
    if request.POST.get("christmas_only"):
        theme, christmas = "", True
    if request.POST.get("stop") or (not theme and not christmas):
        request.session.pop(PREVIEW_SESSION_KEY, None)
        target = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
            target = "panel_seasonal"
        return redirect(target)
    if theme and theme not in THEME_CONFIGS:
        theme = ""
    request.session[PREVIEW_SESSION_KEY] = {"theme": theme or None, "christmas": christmas}
    return redirect("home")


@staff_required
def seasonal_list(request):
    """Décors thématiques et éditions spéciales : état du jour et réglage des périodes."""
    today = timezone.localdate()
    by_key = SeasonalEvent.all_by_key()  # crée les décors manquants
    events = sorted(
        SeasonalEvent.objects.all(),
        key=lambda e: (e.key in SPECIAL_EDITIONS, EDITION_PRIORITY.index(e.key) if e.key in SPECIAL_EDITIONS else 0),
    )

    # Édition spéciale réellement affichée aujourd'hui (la première active dans l'ordre de priorité)
    shown_edition = next(
        (by_key[key] for key in EDITION_PRIORITY if key in by_key and by_key[key].is_active(today)), None
    )

    edited_key = request.POST.get('key') if request.method == 'POST' else None
    cards = []
    for event in events:
        if event.key == edited_key:
            form = SeasonalEventForm(request.POST, instance=event, prefix=event.key)
            if form.is_valid():
                form.save()
                messages.success(request, f"« {event} » mis à jour.")
                return redirect('panel_seasonal')
        else:
            form = SeasonalEventForm(instance=event, prefix=event.key, today=today)
        label, tone, detail = _status(event, today, shown_edition)
        info = EVENT_INFO.get(event.key, {"icon": "✨", "kind": "Décor", "description": ""})
        cards.append({
            'event': event,
            'form': form,
            'info': info,
            'status': label,
            'tone': tone,
            'detail': detail,
            'period': _period_label(event),
            'priority': EDITION_PRIORITY.index(event.key) + 1 if event.key in SPECIAL_EDITIONS else None,
            'open': event.key == edited_key,  # formulaire en erreur : on le garde ouvert
        })

    christmas = by_key.get(SeasonalEvent.CHRISTMAS)
    preview_editions, preview_themes = preview_choices()
    return render(request, 'panel/seasonal.html', {
        'preview_editions': preview_editions,
        'preview_themes': preview_themes,
        'cards': cards,
        'today': today,
        'shown_edition': shown_edition,
        'shown_edition_icon': EVENT_INFO.get(shown_edition.key, {}).get('icon') if shown_edition else '',
        'christmas_today': christmas.is_active(today) if christmas else False,
    })
