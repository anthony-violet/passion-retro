from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Category, Item
from .services import (SHOWCASE_SIZE, ShopError, equipped_items, purchase, toggle_featured,
                       toggle_showcase)

SORTS = {
    'prix': ('Prix croissant', lambda item: (item.sale_price, item.name.lower())),
    'prix-desc': ('Prix décroissant', lambda item: (-item.sale_price, item.name.lower())),
    'rarete': ('Rareté', lambda item: (-item.rarity_rank, item.sale_price)),
    'nouveautes': ('Nouveautés', lambda item: (-item.created_at.timestamp(), item.name.lower())),
}
DEFAULT_SORT = 'rarete'


def _selected_category(request, categories):
    try:
        wanted = int(request.GET.get('categorie', ''))
    except ValueError:
        return None
    return next((category for category in categories if category.pk == wanted), None)


def home(request):
    now = timezone.now()
    items = list(Item.objects.on_sale(now).select_related('category'))
    category_ids = {item.category_id for item in items}
    categories = [c for c in Category.objects.filter(is_active=True) if c.pk in category_ids]
    current = _selected_category(request, categories)
    if current:
        items = [item for item in items if item.category_id == current.pk]
    if request.GET.get('filtre') == 'promos':
        items = [item for item in items if item.on_discount]
    elif request.GET.get('filtre') == 'themes':
        items = [item for item in items if item.kind == Item.KIND_THEME]
    elif request.GET.get('filtre') == 'limites':
        items = [item for item in items if item.is_limited]

    sort = request.GET.get('tri') if request.GET.get('tri') in SORTS else DEFAULT_SORT
    items.sort(key=SORTS[sort][1])

    owned = {}
    if request.user.is_authenticated:
        owned = dict(request.user.inventory.values_list('item_id', 'quantity'))
    for item in items:
        item.owned_quantity = owned.get(item.pk, 0)
        item.equipped = bool(item.owned_quantity) and item.is_equipped_by(request.user)
        item.can_buy = (request.user.is_authenticated and not item.is_sold_out
                        and (item.is_stackable or not item.owned_quantity))
        item.affordable = item.can_buy and request.user.gold >= item.sale_price

    return render(request, 'shop/home.html', {
        'items': items,
        'categories': categories,
        'current_category': current,
        'sorts': [(key, label) for key, (label, _) in SORTS.items()],
        'current_sort': sort,
        'current_filter': request.GET.get('filtre', ''),
        'has_promos': any(i.on_discount for i in Item.objects.on_sale(now)),
    })


@login_required
@require_POST
def buy(request, item_id):
    try:
        item, price = purchase(request.user, item_id)
    except ShopError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Tu as acheté {item.name} pour {price} pièces d'or. "
                                  f"Retrouve-le dans ton inventaire !")
    next_url = request.POST.get('next', '')
    if next_url.startswith('/shop/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect('shop_home')


@login_required
def inventory(request):
    entries = list(request.user.inventory.filter(quantity__gt=0)
                   .select_related('item__category').order_by('item__kind', '-acquired_at'))
    for entry in entries:
        entry.equipped = entry.item.is_equipped_by(request.user)
        entry.featured = entry.item_id == request.user.featured_collectible_id

    kinds = [(code, label) for code, label in Item.KIND_CHOICES
             if any(entry.item.kind == code for entry in entries)]
    current_kind = request.GET.get('type', '')
    if current_kind not in dict(kinds):
        current_kind = ''
    shown = [e for e in entries if not current_kind or e.item.kind == current_kind]

    slots = equipped_items(request.user, entries)
    return render(request, 'shop/inventory.html', {
        'entries': shown,
        'total': len(entries),
        'kinds': kinds,
        'current_kind': current_kind,
        'showcase_count': sum(1 for e in entries if e.showcased and e.item.kind == Item.KIND_COLLECTIBLE),
        'showcase_size': SHOWCASE_SIZE,
        'slots': [
            (Item.KIND_FRAME, "Cadre d'avatar", slots[Item.KIND_FRAME]),
            (Item.KIND_USERNAME, 'Décoration de pseudo', slots[Item.KIND_USERNAME]),
            (Item.KIND_THEME, 'Thème', slots[Item.KIND_THEME]),
        ],
    })


@login_required
@require_POST
def collectible_action(request, item_id):
    """Objet de collection : le mettre en avant à côté du pseudo, ou l'exposer dans la vitrine."""
    action = toggle_showcase if request.POST.get('action') == 'showcase' else toggle_featured
    try:
        messages.success(request, action(request.user, item_id))
    except ShopError as error:
        messages.error(request, str(error))
    next_url = request.POST.get('next', '')
    if next_url.startswith('/shop/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect('shop_inventory')


def my_collection(request):
    """Objets de collection du membre, pour le bouton « Collection » de l'éditeur BBCode."""
    if not request.user.is_authenticated:
        return JsonResponse({'items': [], 'login_required': True})
    entries = (request.user.inventory.filter(quantity__gt=0, item__kind=Item.KIND_COLLECTIBLE)
               .select_related('item').order_by('-acquired_at'))
    return JsonResponse({'items': [
        {'id': entry.pk, 'name': entry.item.name, 'rarity': entry.item.get_rarity_display(),
         'image': entry.item.visual_url}
        for entry in entries
    ]})
