from django.contrib import admin

# admin.py des utilisateurs
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from .models import User, APIKey

# Register your models here.

class UserAdmin(BaseUserAdmin):
    model = User
    fieldsets = (
        (None, {'fields': ('username', 'username_decoration', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email', 'theme', 'avatar', 'border_avatar', 'biography', 'birth_date')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')

    search_fields = ('username', 'email', 'first_name', 'last_name')

admin.site.register(User, UserAdmin)


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'is_active', 'created_at', 'last_used_at', 'expires_at')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('user__username', 'name', 'key_hash')
    readonly_fields = ('key_hash', 'created_at', 'last_used_at')
    fieldsets = (
        (None, {'fields': ('user', 'name', 'is_active')}),
        ('Information cryptographique', {'fields': ('key_hash',), 'description': 'Empreinte SHA-256 de la clé ; la clé brute n\'est jamais affichée'}),
        ('Dates', {'fields': ('created_at', 'last_used_at', 'expires_at')}),
    )