from django.urls import path
from . import views

urlpatterns = [
    # API root
    path('', views.api_root, name='api_root'),
    # Lecture des catégories
    path('categories/', views.list_categories, name='list_categories'),
    
    # Lecture des forums
    path('forums/', views.list_forums, name='list_forums'),
    
    # Lecture/liste des sujets
    path('topics/', views.list_topics, name='list_topics'),
    
    # Détails d'un sujet
    path('topics/<int:topic_id>/', views.get_topic, name='get_topic'),
    
    # Création d'un sujet
    path('topics/create/', views.create_topic, name='create_topic'),
    
    # Création d'un post dans un sujet
    path('topics/<int:topic_id>/posts/', views.create_post, name='create_post'),
]
