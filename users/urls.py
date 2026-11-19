from django.urls import path
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from passion_retro import settings
from . import password_reset, views

urlpatterns = [
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),
    path("activation/renvoyer/", views.resend_activation, name="resend_activation"),
    path("mot-de-passe-oublie/", password_reset.PasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe-oublie/envoye/", password_reset.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "mot-de-passe-oublie/<uidb64>/<token>/",
        password_reset.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("login/", views.login, name="login"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("profile/update/", views.profile_update, name="profile_update"),
    path("profile/contributions/", views.contributions, name="contributions"),
    path("profile/<str:user_id>/", views.another_profile, name="profile"),
    path("contribute/", views.contribute, name="contribute"),
    path("contribute/<str:type>/", views.form_contribute, name="form_contribute"),
    path("new/feature", views.new_feature_user, name="new_feature_user"),
    path("item/use/<int:item_id>/", views.use_item, name="use_item"),
    path("theme/set/<str:theme_name>/", views.set_theme, name="set_theme"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]