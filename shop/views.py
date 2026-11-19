from django.shortcuts import get_object_or_404, render, redirect
from .models import *
from users.models import UserInventory
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Create your views here.
def home(request):
    items = Item.objects.filter(is_active=True) if request.user.is_authenticated else Item.objects.none()
    return render(request, 'shop/home.html', {'items': items})

@login_required
def buy(request, item_id):
    item = get_object_or_404(Item, id=item_id, is_active=True)
    # ON vérifie si l'utilisateur a assez d'argent pour acheter l'item
    if request.user.money >= item.price:
        # On vérifie que l'utilisateur n'a pas déjà acheté l'item
        if not request.user.inventory.filter(item=item).exists():
            # On déduit le prix de l'item de l'argent de l'utilisateur
            gold = UserInventory.objects.filter(user=request.user, item__name='Or').first()
            if gold is not None:
                gold.quantity -= item.price
                gold.save()

            # On ajoute l'item dans l'inventaire de l'utilisateur
            user_inventory = UserInventory.objects.create(user=request.user, item=item)
            user_inventory.quantity = 1
            user_inventory.save()
            messages.success(request, f"Vous avez acheté {item.name} pour {item.price} pièces d'or.")
        else:
            messages.error(request, f"Vous avez déjà acheté {item.name}.")
    else:
        messages.error(request, f"Vous n'avez pas assez d'argent pour acheter {item.name}.")
    return redirect('shop_home')

    