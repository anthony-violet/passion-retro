from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from posts.models import NavSection, Category


@staff_required
def nav_section_list(request):
    sections = NavSection.objects.select_related('category')
    return render(request, 'panel/navigation/sections.html', {'sections': sections})


@staff_required
def nav_section_create(request):
    categories = Category.objects.all().order_by('name')
    if request.method == 'POST':
        label = request.POST.get('label', '').strip()
        category = Category.objects.filter(pk=request.POST.get('category')).first()
        if label and category:
            NavSection.objects.create(
                label=label,
                category=category,
                order=int(request.POST.get('order') or 0),
                visible='visible' in request.POST,
                icon=request.POST.get('icon', '').strip(),
            )
            messages.success(request, "Section créée.")
            return redirect('panel_nav_sections')
        messages.error(request, "Le libellé et la catégorie sont obligatoires.")
    return render(request, 'panel/navigation/section_form.html', {
        'action': 'Créer',
        'categories': categories,
    })


@staff_required
def nav_section_edit(request, section_id):
    section = get_object_or_404(NavSection, pk=section_id)
    categories = Category.objects.all().order_by('name')
    if request.method == 'POST':
        category = Category.objects.filter(pk=request.POST.get('category')).first()
        if not category:
            messages.error(request, "La catégorie est obligatoire.")
            return render(request, 'panel/navigation/section_form.html', {
                'action': 'Modifier',
                'section': section,
                'categories': categories,
            })
        section.label = request.POST.get('label', section.label).strip()
        section.category = category
        section.order = int(request.POST.get('order') or 0)
        section.visible = 'visible' in request.POST
        section.icon = request.POST.get('icon', '').strip()
        section.save()
        messages.success(request, "Section mise à jour.")
        return redirect('panel_nav_sections')
    return render(request, 'panel/navigation/section_form.html', {
        'action': 'Modifier',
        'section': section,
        'categories': categories,
    })


@staff_required
def nav_section_toggle(request, section_id):
    section = get_object_or_404(NavSection, pk=section_id)
    if request.method == 'POST':
        section.visible = not section.visible
        section.save()
        messages.success(request, "Visibilité mise à jour.")
    return redirect('panel_nav_sections')


@staff_required
def nav_section_delete(request, section_id):
    section = get_object_or_404(NavSection, pk=section_id)
    if request.method == 'POST':
        section.delete()
        messages.success(request, "Section supprimée.")
    return redirect('panel_nav_sections')
