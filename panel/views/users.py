from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import Group
from panel.decorators import staff_required
from users.models import User, UserLevel


@staff_required
def user_list(request):
    q = request.GET.get("q", "")
    users = User.objects.order_by("-date_joined")
    if q:
        users = users.filter(username__icontains=q)
    return render(request, "panel/users/list.html", {"users": users, "q": q})


@staff_required
def user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    groups = Group.objects.all()

    if request.method == "POST":
        user.username = request.POST.get("username", user.username)
        user.email = request.POST.get("email", user.email)
        user.first_name = request.POST.get("first_name", "")
        user.last_name = request.POST.get("last_name", "")
        xp = request.POST.get("xp", "").strip()
        if xp:
            try:
                xp = max(0, int(xp))
            except ValueError:
                messages.error(request, "L'XP doit être un nombre entier.")
                return redirect("panel_user_edit", user_id=user.id)
            user_level, _ = UserLevel.objects.get_or_create(user=user)
            user_level.experience = xp
            user_level.save(update_fields=["experience"])

        user.biography = request.POST.get("biography", "")
        user.active = "active" in request.POST
        user.is_staff = "is_staff" in request.POST
        user.is_superuser = "is_superuser" in request.POST
        user.theme = request.POST.get("theme", user.theme)

        new_password = request.POST.get("new_password", "")
        if new_password:
            user.set_password(new_password)

        group_ids = request.POST.getlist("groups")
        user.groups.set(group_ids)

        user.save()
        messages.success(request, f"Utilisateur {user.username} mis à jour.")
        return redirect("panel_user_list")

    themes = [
        ("default", "Thème Défaut (années 2000)"),
        ("retrogame", "Thème Retrogame"),
        ("retrorpg", "Thème RetroRPG"),
        ("80s", "Thème années 80"),
        ("00s", "Thème années 2000 (mobile)"),
    ]
    return render(
        request,
        "panel/users/edit.html",
        {"u": user, "groups": groups, "themes": themes},
    )


@staff_required
@require_POST
def user_toggle_active(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas vous désactiver vous-même.")
        return redirect("panel_user_list")
    user.active = not user.active
    user.save()
    state = "activé" if user.active else "désactivé"
    messages.success(request, f"{user.username} a été {state}.")
    return redirect("panel_user_list")


@staff_required
def user_delete(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas vous supprimer vous-même.")
        return redirect("panel_user_list")
    if request.method == "POST":
        user.delete()
        messages.success(request, "Utilisateur supprimé.")
    return redirect("panel_user_list")
