from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from games.models import LittleBacCategories, LittleBacGames


@staff_required
def games_overview(request):
    categories = LittleBacCategories.objects.all()
    recent_games = LittleBacGames.objects.select_related('author').order_by('-created')[:20]
    return render(request, 'panel/games/overview.html', {'categories': categories, 'recent_games': recent_games})


@staff_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            LittleBacCategories.objects.create(name=name, description=description)
            messages.success(request, "Catégorie créée.")
        return redirect('panel_games')
    return render(request, 'panel/games/category_form.html', {'action': 'Créer'})


@staff_required
def category_edit(request, category_id):
    category = get_object_or_404(LittleBacCategories, pk=category_id)
    if request.method == 'POST':
        category.name = request.POST.get('name', category.name).strip()
        category.description = request.POST.get('description', '').strip()
        category.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect('panel_games')
    return render(request, 'panel/games/category_form.html', {'action': 'Modifier', 'category': category})


@staff_required
def category_delete(request, category_id):
    category = get_object_or_404(LittleBacCategories, pk=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Catégorie supprimée.")
    return redirect('panel_games')
