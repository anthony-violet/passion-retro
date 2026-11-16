import hashlib
import secrets

from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils import timezone
from shop.models import Item


def xp_required(level):
    """XP cumulée nécessaire pour atteindre le niveau ``level``."""
    return int(33.33 * (level ** 2) - 16.66 * level)


LEVEL_TITLES = (
    (1, 'Novice'),
    (5, 'Apprenti'),
    (10, 'Aventurier'),
    (15, 'Chevalier'),
    (20, 'Héros'),
    (30, 'Maître'),
    (40, 'Légende'),
)


def level_title(level):
    """Renvoie le titre associé à un niveau."""
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 1

    title = LEVEL_TITLES[0][1]
    for threshold, label in LEVEL_TITLES:
        if level >= threshold:
            title = label
        else:
            break
    return title


def user_avatar_path(instance, filename):
    return f'avatars/{instance.id}/{filename}'

class User(AbstractUser):
    avatar = models.ImageField(upload_to=user_avatar_path, default='avatars/default.gif')
    email = models.EmailField(unique=False)
    biography = models.TextField(default='Pas de bio')
    favorite_console = models.TextField(blank=True)
    favorite_game = models.TextField(blank=True)
    favorite_game_genre = models.TextField(blank=True)
    anecdote = models.TextField(blank=True)
    # Annonces de nouveautés (voir users/announcements.py)
    last_announcement_seen = models.CharField(max_length=80, blank=True, default='')
    announcement_banner_closed = models.CharField(max_length=80, blank=True, default='')
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=False)
    theme = models.CharField(max_length=50, default='default')
    border_avatar = models.CharField(max_length=50, blank=True, null=True)
    username_decoration = models.CharField(max_length=50, blank=True, null=True)
    show_email = models.BooleanField(default=False)
    website = models.URLField(blank=True, null=True)
    twitter = models.CharField(max_length=100, blank=True, null=True)
    discord = models.CharField(max_length=100, blank=True, null=True)
    youtube = models.CharField(max_length=100, blank=True, null=True)
    last_seen = models.DateTimeField(blank=True, null=True)

    groups = models.ManyToManyField(
        Group,
        related_name='customuser_set',  # Ajoutez un related_name unique
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='customuser_permissions_set',  # Ajoutez un related_name unique
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    @property
    def level(self):
        return self.levels.first()

    @property
    def level_number(self):
        level = self.levels.first()
        return level.level if level else 1

    @property
    def level_title(self):
        return level_title(self.level_number)

    @property
    def experience(self):
        level = self.levels.first()
        return level.experience if level else 0

    @property
    def experience_left(self):
        level = self.levels.first()
        if level is None:
            return xp_required(1)
        return max(0, xp_required(level.level) - level.experience)

    @property
    def inventory(self):
        return self.inventory.all()

    @property
    def money(self):
        entry = self.inventory.filter(item__name='Or').first()
        return entry.quantity if entry else 0

    def __str__(self):
        return self.username
    
    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['username']

class VisitorStats(models.Model):
    total_visitors = models.PositiveIntegerField(default=0)
    last_reset = models.DateTimeField(auto_now=True)

class UserLevel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='levels')
    level = models.PositiveIntegerField(default=1)
    experience = models.PositiveIntegerField(default=0)

    def __str__(self):
        return str(self.level)

    class Meta:
        verbose_name = 'Niveau utilisateur'
        verbose_name_plural = 'Niveaux utilisateurs'
        ordering = ['level']
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_user_level'),
        ]

class UserInventory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inventory')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.item.name

    class Meta:
        verbose_name = 'Inventaire utilisateur'
        verbose_name_plural = 'Inventaires utilisateurs'
        ordering = ['item']


class APIKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, help_text="Nom identifiant la clé (ex: 'OpenClaw production')")
    key_hash = models.CharField(max_length=64, help_text="Empreinte SHA-256 de la clé ; la clé brute n'est jamais stockée.")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Date d'expiration facultative.")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Clé API'
        verbose_name_plural = 'Clés API'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    def is_expired(self):
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])