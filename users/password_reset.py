"""Mot de passe oublié : vues Django avec pages et e-mails du site."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

EMAIL_CONTEXT = {
    'site_name': settings.SITE_NAME,
    'site_url': settings.SITE_URL.rstrip('/'),
}


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'users/password_reset_form.html'
    email_template_name = 'emails/password_reset.txt'
    html_email_template_name = 'emails/password_reset.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    extra_email_context = EMAIL_CONTEXT
    extra_context = {'seo_noindex': True, 'page_title': f"Mot de passe oublié - {settings.SITE_NAME}"}


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'users/password_reset_done.html'
    extra_context = {'seo_noindex': True, 'page_title': f"E-mail envoyé - {settings.SITE_NAME}"}


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('login')
    extra_context = {'seo_noindex': True, 'page_title': f"Nouveau mot de passe - {settings.SITE_NAME}"}

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        # Le lien reçu par e-mail prouve que l'adresse est valide : on active le compte.
        if not user.active:
            user.active = True
            user.save(update_fields=['active'])
        messages.success(self.request, "Ton mot de passe a été modifié. Tu peux te connecter.")
        return response
