from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from .forms import PostForm, UserRegistrationForm, UserLoginForm, UserUpdateForm, ProfileUpdateForm, PasswordUpdateForm
from posts.models import Post
from django.utils.text import slugify
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .models import User
from .leveling import STARTING_GOLD, grant_experience
import urllib.request
import json

def register(request):
    from messagerie.models import PrivateMessageSubject, PrivateMessage
    if request.user.is_authenticated:
        return redirect('profile')
    
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        recaptcha = request.POST.get('g-recaptcha-response')
        if form.is_valid():

            url = 'https://www.google.com/recaptcha/api/siteverify'
            values = {
                'secret': settings.GOOGLE_PRIVATE_KEY,
                'response': recaptcha
            }
            data = urllib.parse.urlencode(values).encode()
            req =  urllib.request.Request(url, data=data)
            response = urllib.request.urlopen(req)
            result = json.loads(response.read().decode())

            if result['success']:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password1'],
                    theme='00s',
                    active=True
                )

                messages.success(request, f"Bonjour et bienvenue {user.username} ! Ton compte a été créé avec succès. Tu peux désormais te connecter.")

                subject = PrivateMessageSubject.objects.create(
                    receiver=user,
                    sender=User.objects.get(username='RetroBot'),
                    subject=f"Bienvenue sur {settings.SITE_NAME} !"
                )

                PrivateMessage.objects.create(
                    subject=subject,
                    author=User.objects.get(username='RetroBot'),
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
[b]L'équipe {settings.SITE_NAME}[/b]""")

                return redirect('login')
            else:
                messages.error(request, f"On y est presque ! Vérifie bien le captcha pour finaliser ton inscription.")            

    form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form, 'GOOGLE_PUBLIC_KEY': settings.GOOGLE_PUBLIC_KEY})

def register_with_token(request):
    # Si l'utilisateur est deja connecté, on le redirige vers la page de pr>
    if request.user.is_authenticated:
        return redirect('profile')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1']
            )
            genToken = PasswordResetTokenGenerator()
            token = genToken.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            activation_link = request.build_absolute_uri(f"/users/activate/{uid}/{token}")
           
            email_subject = 'Activation de votre compte'
            email_body = render_to_string('emails/activation_account.html', {
                'user': user,
                'activation_link': activation_link,
            })

            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            messages.success(request, f"Ton compte a été créé avec succès, {user.username}! Un email d'activation t'a été envoyé pour valider ton inscription.")

            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})

def activate(request, uidb64, token):
    uid = None  # Initialisation de la variable uid
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_generator = PasswordResetTokenGenerator()
    if user is not None and token_generator.check_token(user, token):
        user.active = True
        user.save()
        messages.success(request, "Votre compte a été activé avec succès.")
        return redirect('login')
    else:
        messages.error(request, "Le lien d'activation est invalide.")
        return redirect('register')

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
            
            if user.active == False:
                messages.error(request, "Votre compte n'est pas activé. Veuillez vérifier votre boîte mail.")
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

    if not request.user.inventory.exists():
        from shop.models import Item
        gold_item = Item.objects.filter(name='Or').first() or Item.objects.order_by('pk').first()
        if gold_item is not None:
            request.user.inventory.get_or_create(item=gold_item, defaults={'quantity': STARTING_GOLD})
    return render(request, "features/new_feature_user_inventory.html")

@login_required
def use_item(request, item_id):
    item = request.user.inventory.get(item_id=item_id)

    # On slugify le nom de l'item pour l'utiliser dans les conditions
    item_name = slugify(item.item.name)

    if item.quantity > 0:
        if item.item.category.name == 'cadres':
            request.user.border_avatar = item_name
        
        if item.item.category.name == 'themes':
            request.user.theme_active = item_name

        if item.item.category.name == 'Décoration pseudo':
            request.user.username_decoration = item_name
        
        request.user.save()
        
        messages.success(request, f"Vous avez utilisé {item.item.name}.")
    else:
        messages.error(request, f"Vous n'avez pass de {item.item.name}.")
    return redirect('profile')

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
