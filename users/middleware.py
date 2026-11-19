# yourapp/middleware.py
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from . import visits
from .models import User, VisitorStats
from django.utils.deprecation import MiddlewareMixin

# On vérifie que l'user existe dans la table  user_level. Si pas, on le redirige vers la page tuto de la nouvelle feature
class UserLevelMiddleware(MiddlewareMixin):
    # On vérifie que l'on est pas sur la page de tuto de la nouvelle feature
    def process_request(self, request):
        if not request.user.is_authenticated:
            return

        if request.path == '/users/new/feature':
            return

        if not request.user.levels.exists():
            return redirect('new_feature_user')

        if not request.user.inventory.exists():
            return redirect('new_feature_user')


class UserLevelUpMiddleware(MiddlewareMixin):
    """Garde le middleware pour compatibilité : les passages de niveau sont
    désormais gérés par ``users.leveling.grant_experience``. ``experience_left``
    est une propriété du modèle ``User`` et n'a plus besoin d'être calculée ici."""

    def process_request(self, request):
        return None

class UserStatsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Nombre total d'utilisateurs
        total_users = User.objects.count()
        
        # Dernier utilisateur inscrit
        last_user = User.objects.latest('date_joined') if total_users > 0 else None
        
        # Visiteurs actifs (membres compris) sur les 5 dernières minutes
        current_time = timezone.now()
        if not visits.is_bot(request):
            visits.record(request, current_time)
        visitor_count = visits.active_visitor_count(current_time)

        # Gestion du total des visiteurs
        stats, created = VisitorStats.objects.get_or_create(pk=1)
        total_visitor_count = stats.total_visitors

        # Membres en ligne (activité dans les 5 dernières minutes)
        online_cutoff = current_time - timedelta(minutes=5)
        if request.user.is_authenticated:
            User.objects.filter(pk=request.user.pk).update(last_seen=current_time)
            request.user.last_seen = current_time
        online_member_ids = set(
            User.objects.filter(last_seen__gte=online_cutoff)
            .values_list('id', flat=True)
        )
        online_members_count = len(online_member_ids)

        # Si l'utilisateur est authentifié
        if request.user.is_authenticated:
            theme_active = request.user.theme
        else:
            theme_active = '00s'
        
        # Ajouter les variables à l'objet request
        request.total_users = total_users
        request.last_user = last_user
        request.visitor_count = visitor_count
        request.total_visitor_count = total_visitor_count
        request.online_members = online_members_count
        request.online_member_ids = online_member_ids
        request.theme_active = theme_active

class AnnouncementMiddleware(MiddlewareMixin):
    """Redirige une seule fois chaque membre vers l'annonce de nouveauté en cours.

    Uniquement pour une navigation classique (GET d'une page HTML) : jamais
    pendant un envoi de formulaire, un appel AJAX ou sur l'admin.
    """

    def process_request(self, request):
        from . import announcements

        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or request.method != 'GET':
            return None
        if announcements.has_seen(user):
            return None
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return None
        if 'text/html' not in request.headers.get('accept', ''):
            return None
        if request.path.startswith(announcements.EXCLUDED_PREFIXES):
            return None
        return redirect('announcement')
