from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='shop_home'),
    path('buy/<int:item_id>/', views.buy, name='shop_buy'),
    path('inventaire/', views.inventory, name='shop_inventory'),
    path('inventaire/collection/<int:item_id>/', views.collectible_action, name='shop_collectible_action'),
    path('inventaire/ma-collection.json', views.my_collection, name='shop_my_collection'),
]
