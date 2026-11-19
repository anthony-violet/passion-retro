import re

from django.contrib import messages
from django.db.models import Case, IntegerField, Max, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import redirect, render

from panel.decorators import staff_required
from shop.models import Item
from users.models import StaffReward, User
from users.rewards import give_reward

MAX_XP = 100000
MAX_GOLD = 100000


def _parse_int(value, label, maximum, errors):
    value = (value or '').strip()
    if not value:
        return 0
    try:
        number = int(value)
    except ValueError:
        errors.append(f"{label} doit être un nombre entier.")
        return 0
    if number < 0 or number > maximum:
        errors.append(f"{label} doit être compris entre 0 et {maximum}.")
        return 0
    return number


@staff_required
def reward_list(request):
    items = Item.objects.order_by('name')
    form = {
        'usernames': request.GET.get('user', ''),
        'reason': '', 'experience': '', 'gold': '', 'item': '', 'notify': True,
    }

    if request.method == 'POST':
        form = {
            'usernames': request.POST.get('usernames', ''),
            'reason': request.POST.get('reason', '').strip(),
            'experience': request.POST.get('experience', ''),
            'gold': request.POST.get('gold', ''),
            'item': request.POST.get('item', ''),
            'notify': bool(request.POST.get('notify')),
        }
        errors = []
        names = [n for n in re.split(r'[\s,;]+', form['usernames']) if n]
        names = list(dict.fromkeys(names))  # sans doublons, ordre conservé
        if not names:
            errors.append("Indique au moins un membre.")
        if not form['reason']:
            errors.append("Indique le motif de la récompense (ex. « Concours de Noël »).")
        elif len(form['reason']) > 150:
            errors.append("Le motif ne doit pas dépasser 150 caractères.")
        experience = _parse_int(form['experience'], "L'XP", MAX_XP, errors)
        gold = _parse_int(form['gold'], "L'or", MAX_GOLD, errors)
        item = None
        if form['item']:
            item = items.filter(pk=form['item']).first() if form['item'].isdigit() else None
            if item is None:
                errors.append("Objet introuvable.")
        if not (experience or gold or item):
            errors.append("Choisis au moins une récompense : XP, or ou objet.")

        users = []
        if names:
            query = Q()
            for name in names:
                query |= Q(username__iexact=name)
            found = {u.username.lower(): u for u in User.objects.filter(query)}
            missing = [n for n in names if n.lower() not in found]
            if missing:
                errors.append("Membre(s) introuvable(s) : " + ", ".join(missing))
            users = [found[n.lower()] for n in names if n.lower() in found]

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            rewarded, skipped = [], []
            for user in users:
                reward = give_reward(user, request.user, form['reason'], experience, gold,
                                     item, notify=form['notify'])
                (rewarded if reward else skipped).append(user.username)
            if rewarded:
                messages.success(request, "Récompense attribuée à : " + ", ".join(rewarded))
            if skipped:
                messages.warning(request, "Rien à donner (objet déjà possédé) pour : " + ", ".join(skipped))
            return redirect('panel_rewards')

    rewards = StaffReward.objects.select_related('user', 'given_by', 'item')[:50]
    return render(request, 'panel/rewards/list.html', {
        'form': form, 'items': items, 'rewards': rewards,
    })


@staff_required
def member_search(request):
    """Suggestions de membres pour le sélecteur de la page Récompenses."""
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})
    users = (
        User.objects.filter(username__icontains=q)
        .exclude(username='RetroBot')
        .annotate(
            starts=Case(When(username__istartswith=q, then=Value(0)),
                        default=Value(1), output_field=IntegerField()),
            max_level=Max('levels__level'),
        )
        .order_by('starts', 'username')[:10]
    )
    results = []
    for user in users:
        try:
            avatar = user.avatar.url if user.avatar else ''
        except ValueError:
            avatar = ''
        results.append({
            'username': user.username,
            'level': user.max_level or 1,
            'avatar': avatar,
            'active': user.active,
        })
    return JsonResponse({'results': results})
