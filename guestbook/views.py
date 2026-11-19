from django.conf import settings
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import redirect, render
from .models import Guestbook
from . import antispam
from .forms import CreateGuestbook

def guestbook_home(request):
    # Si un message est envoyé on le traite
    if request.method == "POST":
        form = CreateGuestbook(request.POST)
        if form.is_bot:
            # On ne dit rien au robot : il croit avoir réussi.
            return redirect('guestbook_home')
        fingerprint = antispam.ip_fingerprint(request)
        is_staff = request.user.is_authenticated and request.user.is_staff
        if not is_staff and antispam.too_many_messages(fingerprint):
            messages.error(
                request,
                "Vous avez déjà laissé plusieurs messages récemment. Réessayez dans une heure.",
            )
        elif form.is_valid():
            Guestbook.objects.create(
                author=form.cleaned_data['author'],
                content=form.cleaned_data['content'],
                ip_hash=fingerprint,
            )
            messages.success(request, "Merci pour votre message !")
            return redirect('guestbook_home')
    else:
        form = CreateGuestbook()
    
    guestbook = Guestbook.objects.filter(active=True).order_by('-created')
    paginator = Paginator(guestbook, 10)

    page_number = request.GET.get('page')
    guestbook = paginator.get_page(page_number)

    context = {
        'guestbook': guestbook,
        'is_paginated': guestbook.has_other_pages(),
        'page_obj': guestbook,
        'paginator': paginator,
        'form': form,
        'page_title': f"Livre d'Or - {settings.SITE_NAME}",
        'page_heading': "Livre d'Or",
        'page_description': (
            "Laissez un message aux visiteurs et à la communauté de "
            f"{settings.SITE_NAME}, le portail de la culture rétro."
        ),
    }

    return render(request, "components/guestbook_home.html", context)