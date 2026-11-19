from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from shop.models import Category, Item


@staff_required
def shop_overview(request):
    categories = Category.objects.prefetch_related('items').order_by('position', 'name')
    return render(request, 'panel/shop/overview.html', {'categories': categories})


@staff_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            Category.objects.create(name=name, description=description,
                                    position=_parse_int(request.POST.get('position')))
            messages.success(request, "Catégorie créée.")
        return redirect('panel_shop')
    return render(request, 'panel/shop/category_form.html', {'action': 'Créer'})


@staff_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name', category.name).strip()
        category.description = request.POST.get('description', '').strip()
        category.is_active = 'is_active' in request.POST
        category.position = _parse_int(request.POST.get('position'), default=category.position)
        category.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect('panel_shop')
    return render(request, 'panel/shop/category_form.html', {'action': 'Modifier', 'category': category})


@staff_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Catégorie supprimée.")
    return redirect('panel_shop')


def _parse_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _parse_int(value, default=0, minimum=0, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    number = max(minimum, number)
    return min(number, maximum) if maximum is not None else number


def _fill_item(item, request):
    """Remplit ``item`` depuis le formulaire du panel."""
    post = request.POST
    item.name = post.get('name', item.name or '').strip()
    item.description = post.get('description', '').strip()
    item.category_id = post.get('category') or item.category_id
    item.kind = post.get('kind') if post.get('kind') in dict(Item.KIND_CHOICES) else item.kind
    item.rarity = post.get('rarity') if post.get('rarity') in dict(Item.RARITY_CHOICES) else item.rarity
    item.css_class = slugify(post.get('css_class', '')) if item.kind != Item.KIND_THEME else post.get('css_class', '').strip()
    item.price = _parse_int(post.get('price'), default=item.price or 0)
    stock = post.get('stock', '').strip()
    item.stock = _parse_int(stock) if stock else None
    item.available_from = _parse_datetime(post.get('available_from'))
    item.available_until = _parse_datetime(post.get('available_until'))
    item.discount_percent = _parse_int(post.get('discount_percent'), maximum=90)
    item.discount_from = _parse_datetime(post.get('discount_from'))
    item.discount_until = _parse_datetime(post.get('discount_until'))
    item.effect = post.get('effect') if post.get('effect') in dict(Item.EFFECT_CHOICES) else ''
    item.effect_hours = _parse_int(post.get('effect_hours'), default=24, minimum=1, maximum=24 * 30)
    item.is_active = 'is_active' in post
    if request.FILES.get('image'):
        item.image = request.FILES['image']


def _item_form(request, item, action):
    return render(request, 'panel/shop/item_form.html', {
        'action': action, 'item': item,
        'categories': Category.objects.filter(is_active=True),
        'kinds': Item.KIND_CHOICES, 'rarities': Item.RARITY_CHOICES, 'effects': Item.EFFECT_CHOICES,
    })


@staff_required
def item_create(request):
    item = Item(kind=Item.KIND_COLLECTIBLE)
    if request.method == 'POST':
        _fill_item(item, request)
        if item.name and item.category_id:
            item.save()
            messages.success(request, "Item créé.")
            return redirect('panel_shop')
        messages.error(request, "Le nom et la catégorie sont obligatoires.")
    return _item_form(request, item, 'Créer')


@staff_required
def item_edit(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if request.method == 'POST':
        _fill_item(item, request)
        if item.name:
            item.save()
            messages.success(request, "Item mis à jour.")
            return redirect('panel_shop')
        messages.error(request, "Le nom est obligatoire.")
    return _item_form(request, item, 'Modifier')


@staff_required
def item_delete(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Item supprimé.")
    return redirect('panel_shop')
