from django.utils.deprecation import MiddlewareMixin
from .models import Post, NavSection

class PostsMiddleware(MiddlewareMixin):
    def process_request(self, request):

        # On récupère tous les posts de type 'games'
        posts_games = Post.objects.filter(type='games', active=True, parent=True)

        # On récupère tous les posts de type 'movies'
        posts_movies = Post.objects.filter(type='movies', active=True, parent=True)

        # On récupère tous les posts de type 'music'
        posts_music = Post.objects.filter(type='music', active=True, parent=True)

        # On récupère tous les posts de type 'tech'
        posts_tech = Post.objects.filter(type='tech', active=True, parent=True)

        # on met tout ça dans l'objet request
        request.posts_games = posts_games
        request.posts_movies = posts_movies
        request.posts_music = posts_music
        request.posts_tech = posts_tech

        # Sections de la navbar gérées depuis le panel
        nav_sections = []
        for section in NavSection.objects.filter(visible=True).select_related('category'):
            if not section.category_id:
                continue
            nav_sections.append({
                'label': section.label,
                'icon': section.icon,
                'category': section.category,
                'posts': Post.objects.filter(
                    category=section.category, active=True, parent=True
                ),
            })

        request.nav_sections = nav_sections
