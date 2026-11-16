from django.urls import path
from . import views

app_name = 'ephemerides'

urlpatterns = [
    path('', views.ephemeride_today, name='ephemerides_today'),
    path('contribute/', views.contribute_ephemeride, name='contribute_ephemeride'),
]
