from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from shop.models import Category, Item


@staff_required
def shop_overview(request):
    categories = Category.objects.prefetch_related('items').order_by('name')
    return render(request, 'panel/shop/overview.html', {'categories': categories})


@staff_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            Category.objects.create(name=name, description=description)
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


@staff_required
def item_create(request):
    categories = Category.objects.filter(is_active=True)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip() or 0
        category_id = request.POST.get('category')
        image = request.FILES.get('image')
        if name and category_id:
            item = Item(name=name, description=description, price=price, category_id=category_id)
            if image:
                item.image = image
            item.save()
            messages.success(request, "Item créé.")
        return redirect('panel_shop')
    return render(request, 'panel/shop/item_form.html', {'action': 'Créer', 'categories': categories})


@staff_required
def item_edit(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    categories = Category.objects.filter(is_active=True)
    if request.method == 'POST':
        item.name = request.POST.get('name', item.name).strip()
        item.description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        item.price = price if price else item.price
        item.category_id = request.POST.get('category', item.category_id)
        item.is_active = 'is_active' in request.POST
        if request.FILES.get('image'):
            item.image = request.FILES['image']
        item.save()
        messages.success(request, "Item mis à jour.")
        return redirect('panel_shop')
    return render(request, 'panel/shop/item_form.html', {'action': 'Modifier', 'item': item, 'categories': categories})


@staff_required
def item_delete(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Item supprimé.")
    return redirect('panel_shop')
