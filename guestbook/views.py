from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Guestbook
from .forms import CreateGuestbook

def guestbook_home(request):
    # Si un message est envoyé on le traite
    if request.method == "POST":
        form = CreateGuestbook(request.POST)
        if form.is_valid():
            author = form.cleaned_data['author']
            content = form.cleaned_data['content']
            Guestbook.objects.create(author=author, content=content)
    
    guestbook = Guestbook.objects.all().order_by('-created')
    paginator = Paginator(guestbook, 10)

    page_number = request.GET.get('page')
    guestbook = paginator.get_page(page_number)

    context = {
        'guestbook': guestbook,
        'is_paginated': guestbook.has_other_pages(),
        'page_obj': guestbook,
        'paginator': paginator,
        'form': CreateGuestbook(),
        'page_title': f"Livre d'Or - {settings.SITE_NAME}",
        'page_heading': "Livre d'Or",
        'page_description': (
            "Laissez un message aux visiteurs et à la communauté de "
            f"{settings.SITE_NAME}, le portail de la culture rétro."
        ),
    }

    return render(request, "components/guestbook_home.html", context)