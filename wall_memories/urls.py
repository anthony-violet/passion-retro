from django.urls import path

from . import views

app_name = 'wall_memories'

urlpatterns = [
    path('', views.wall, name='wall'),
    path('partager/', views.create, name='create'),
    path('au-hasard/', views.random_memory, name='random'),
    path('mes-souvenirs/', views.mine, name='mine'),
    path('mes-favoris/', views.favorites, name='favorites'),
    path('<int:pk>/modifier/', views.edit, name='edit'),
    path('<int:pk>/supprimer/', views.delete, name='delete'),
    path('<int:pk>/reagir/', views.react, name='react'),
    path('<int:pk>/favori/', views.toggle_favorite, name='favorite'),
    path('<int:pk>/commenter/', views.add_comment, name='comment'),
    path('commentaire/<int:pk>/supprimer/', views.delete_comment, name='delete_comment'),
    path('<int:pk>/', views.detail, name='detail_short'),
    path('<int:pk>/<slug:slug>/', views.detail, name='detail'),
]
