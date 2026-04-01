from django.urls import path
from . import views

urlpatterns = [
    path('', views.ephemeride_today, name='ephemerides_today'),
]
