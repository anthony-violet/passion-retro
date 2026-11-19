from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
from . import accounts
from .forms import PostForm, ResendActivationForm, UserRegistrationForm, UserLoginForm, UserUpdateForm, ProfileUpdateForm, PasswordUpdateForm
from posts.models import Post
from django.utils.http import url_has_allowed_host_and_scheme
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from .models import User
from .leveling import grant_experience, grant_starting_gold
import urllib.parse
import urllib.request
import json

def _recaptcha_ok(request):
    """Vérifie le reCAPTCHA. Sans clé configurée en développement, on laisse passer."""
    if not settings.GOOGLE_PRIVATE_KEY:
        return settings.DEBUG
    data = urllib.parse.urlencode({
        'secret': settings.GOOGLE_PRIVATE_KEY,
        'response': request.POST.get('g-recaptcha-response', ''),
    }).encode()
    try:
        req = urllib.request.Request('https://www.google.com/recaptcha/api/siteverify', data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            return bool(json.loads(response.read().decode()).get('success'))
    except (OSError, ValueError):
        return False


def _send_welcome_message(user):
    from messagerie.models import PrivateMessage, PrivateMessageSubject

    bot = User.objects.filter(username='RetroBot').first()
    if bot is None:
        return
    subject = PrivateMessageSubject.objects.create(
        receiver=user,
        sender=bot,
        subject=f"Bienvenue sur {settings.SITE_NAME} !",
    )
    PrivateMessage.objects.create(
        subject=subject,
        author=bot,
        message=f"""[b]Bienvenue sur {settings.SITE_NAME} ![/b]

Salut [b]{user.username}[/b] !,

Merci de nous avoir rejoints dans cette aventure dédiée aux passionnés de rétro ! Que tu sois fan de consoles vintage, collectionneur d'objets d'époque ou simple curieux, tu es ici chez toi. 

✨ [b]Découvre tout ce que {settings.SITE_NAME} a à offrir :[/b]  
Plonge dans nos articles pour en apprendre plus sur les trésors du passé, participe aux discussions sur le forum et teste tes connaissances avec nos jeux rétro. Chaque section est là pour te permettre de partager ta passion et d'en apprendre davantage.  

🚀 [b]Rejoins la communauté :[/b]  
Ton avis et tes contributions sont précieux ! N’hésite pas à lancer une discussion sur le forum, à réagir aux articles ou à défier les autres membres sur nos jeux. Plus nous sommes actifs, plus l’expérience sera enrichissante pour tous.  

Si tu as des questions ou des suggestions pour améliorer le site, contacte-nous. Nous sommes là pour t'accompagner !  

Encore une fois, bienvenue parmi nous et prépare-toi à replonger dans l’univers du rétro !  

À bientôt,  
[b]L'équipe {settings.SITE_NAME}[/b]""",
    )


def register(request):
    if request.user.is_authenticated:
        return redirect('profile')

    form = UserRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not _recaptcha_ok(request):
            messages.error(request, "On y est presque ! Vérifie bien le captcha pour finaliser ton inscription.")
        else:
            # Le compte reste désactivé tant que l'adresse e-mail n'est pas validée.
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
                theme='00s',
                active=False,
            )
            _send_welcome_message(user)
            if accounts.send_activation_email(user):
                messages.success(
                    request,
                    f"Bienvenue {user.username} ! Ton compte est créé : clique sur le lien "
                    f"envoyé à {user.email} pour l'activer, puis connecte-toi.",
                )
            else:
                messages.warning(
                    request,
                    "Ton compte est créé, mais l'e-mail d'activation n'a pas pu partir. "
                    "Redemande-le depuis la page « Renvoyer l'e-mail d'activation ».",
                )
            return redirect('login')

    return render(request, 'users/register.html', {'form': form, 'GOOGLE_PUBLIC_KEY': settings.GOOGLE_PUBLIC_KEY})


def activate(request, uidb64, token):
    user = accounts.user_from_uid(uidb64)
    if user is not None and user.active:
        messages.info(request, "Ton compte est déjà activé, tu peux te connecter.")
        return redirect('login')
    if user is None or not accounts.activation_token.check_token(user, token):
        messages.error(
            request,
            "Ce lien d'activation est invalide ou a expiré. Demande un nouveau lien ci-dessous.",
        )
        return redirect('resend_activation')

    user.active = True
    user.save(update_fields=['active'])
    messages.success(request, "Ton compte est activé ! Tu peux maintenant te connecter.")
    return redirect('login')


def resend_activation(request):
    if request.user.is_authenticated:
        return redirect('profile')

    form = ResendActivationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.filter(email__iexact=form.cleaned_data['email'], active=False).first()
        if user is not None:
            accounts.send_activation_email(user)
        # Même réponse dans tous les cas : on ne révèle pas quelles adresses sont inscrites.
        messages.success(
            request,
            "Si un compte non activé correspond à cette adresse, un nouveau lien d'activation vient d'y être envoyé.",
        )
        return redirect('login')

    return render(request, 'users/resend_activation.html', {
        'form': form,
        'page_title': f"Renvoyer l'e-mail d'activation - {settings.SITE_NAME}",
        'seo_noindex': True,
    })


def login(request):
    if request.method == 'POST':
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is None:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
                return redirect('login')
            
            if not user.active:
                messages.error(
                    request,
                    "Ton compte n'est pas encore activé : clique sur le lien reçu par e-mail. "
                    "Rien reçu ? Utilise « Renvoyer l'e-mail d'activation ».",
                )
                return redirect('login')
            
            auth_login(request, user)
            messages.success(request, f"Bienvenue, {username}!")
            return redirect('home')
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})

def _profile_context(user):
    from forum.models import Topic
    from forum.models import Post as ForumPost
    from posts.models import Post as Article
    return {
        'user': user,
        'topics': Topic.objects.filter(author=user).count(),
        'forum_posts': ForumPost.objects.filter(author=user).count(),
        'posts': Article.objects.filter(author=user).count(),
        'memories': _published_memories(user),
    }


def _published_memories(user):
    from wall_memories.models import Memory
    return (
        Memory.objects.filter(author=user, status=Memory.STATUS_PUBLISHED)
        .order_by('-published_at')
    )

def profile(request):
    try:
        user = User.objects.get(id=request.user.id)
    except User.DoesNotExist:
        from django.contrib.auth import logout
        logout(request)
        return redirect('login')
    return render(request, 'users/profile.html', _profile_context(user))

def another_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    return render(request, 'users/profile.html', _profile_context(user))

@login_required(login_url='login')
def profile_update(request):
    user_form = UserUpdateForm(instance=request.user)
    password_form = PasswordUpdateForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'profile':
            user_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, 'Profil mis à jour avec succès !')
                return redirect('profile_update')

        elif action == 'password':
            password_form = PasswordUpdateForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Mot de passe modifié avec succès !')
                return redirect('profile_update')

    return render(request, 'users/profile_update.html', {
        'user_form': user_form,
        'password_form': password_form,
    })

@login_required
def contribute(request):
    from posts.utils import contribution_categories
    from posts.models import NavSection

    icons = {
        section.category_id: section.icon
        for section in NavSection.objects.filter(visible=True)
    }
    rubriques = [
        {'category': cat, 'label': label, 'icon': icons.get(cat.id, '')}
        for cat, label in contribution_categories()
    ]
    return render(request, "users/contribute.html", {'rubriques': rubriques})


@login_required(login_url='register')
def form_contribute(request, type):
    from posts.views import contribution_form

    return contribution_form(request, type)


@login_required()
def contributions(request):
    posts = (
        Post.objects.filter(author=request.user, parent=True)
        .select_related('category')
        .prefetch_related('child_posts')
        .order_by('-created')
    )

    return render(request, "users/contributions.html", {'posts':posts})

@login_required
def new_feature_user(request):
    # On créer une entree dans la table user_level pour l'utilisateur si il n'en a pas
    if not request.user.levels.exists():
        request.user.levels.create(level=1)
        return render(request, "features/new_feature_user_level.html")

    grant_starting_gold(request.user)
    return render(request, "features/new_feature_user_inventory.html")

@login_required
@require_POST
def use_item(request, item_id):
    """Équipe un objet de l'inventaire, le retire s'il est déjà équipé, ou le consomme."""
    from shop.services import ShopError, use_item as use_inventory_item

    try:
        messages.success(request, use_inventory_item(request.user, item_id))
    except ShopError as error:
        messages.error(request, str(error))
    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('shop_inventory')

@login_required
def set_theme(request, theme_name):
    """Vue pour changer le thème directement depuis le menu"""
    available_themes = ["default", "rpg", "retrorpg", "80s", "00s", "vhs", "modern"]
    if theme_name in available_themes:
        request.user.theme = theme_name
        request.user.save()
        request.theme_active = theme_name
    return redirect(request.META.get("HTTP_REFERER", "/"))

def announcement(request):
    """Page publique de la nouveauté en cours ; les membres reçoivent leur cadeau la première fois."""
    from django.http import Http404
    from . import announcements

    current = announcements.current()
    if not current:
        raise Http404
    gift_xp = announcements.mark_seen(request.user) if request.user.is_authenticated else 0
    return render(request, current['template'], {
        'announcement': current,
        'gift_xp': gift_xp,
        'page_title': f"Nouveauté : {current['title']} - {settings.SITE_NAME}",
        'page_description': current['banner'],
    })


def close_announcement_banner(request):
    """Ferme le bandeau de nouveauté (sur le compte du membre, ou par cookie pour un visiteur)."""
    from django.http import JsonResponse
    from django.utils.http import url_has_allowed_host_and_scheme
    from . import announcements

    current = announcements.current()
    if request.method != 'POST' or not current:
        return redirect('home')
    if request.user.is_authenticated:
        User.objects.filter(pk=request.user.pk).update(announcement_banner_closed=current['key'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        response = JsonResponse({'closed': True})
    else:
        target = request.POST.get('next', '')
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
            target = '/'
        response = redirect(target)
    response.set_cookie(
        announcements.BANNER_COOKIE, current['key'],
        max_age=60 * 60 * 24 * 180, samesite='Lax', secure=request.is_secure(),
    )
    return response
