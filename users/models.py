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
    # Porte-monnaie : pièces d'or gagnées et dépensées en boutique.
    gold = models.PositiveIntegerField("Or", default=0)
    starting_gold_given = models.BooleanField(default=False)
    # Fin du boost d'XP x2 obtenu avec un consommable de la boutique.
    xp_boost_until = models.DateTimeField(blank=True, null=True)
    # Objet de collection mis en avant à côté du pseudo (forum, livre d'or…).
    featured_collectible = models.ForeignKey(
        Item, verbose_name="Objet fétiche", on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

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
    def money(self):
        return self.gold

    @property
    def has_xp_boost(self):
        return bool(self.xp_boost_until and self.xp_boost_until > timezone.now())

    def __str__(self):
        return self.username
    
    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['username']

class VisitorStats(models.Model):
    total_visitors = models.PositiveIntegerField(default=0)
    last_reset = models.DateTimeField(auto_now=True)


class Visit(models.Model):
    """Une visite sur le site (statistiques internes, sans Google Analytics).

    Une visite se termine après 30 minutes d'inactivité ; le même visiteur
    (``visitor_id``, gardé en session) peut donc en faire plusieurs. L'adresse
    IP n'est jamais enregistrée : seul le pays qui en est déduit est conservé.
    """

    visitor_id = models.CharField(max_length=32, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='visits')
    started = models.DateTimeField(db_index=True)
    last_seen = models.DateTimeField(db_index=True)
    landing_path = models.CharField(max_length=255, blank=True, default='')
    current_path = models.CharField(max_length=255, blank=True, default='')
    referrer = models.CharField(max_length=255, blank=True, default='')
    referrer_domain = models.CharField(max_length=120, blank=True, default='', db_index=True)
    country = models.CharField(max_length=2, blank=True, default='', db_index=True)
    utm_source = models.CharField(max_length=100, blank=True, default='', db_index=True)
    utm_medium = models.CharField(max_length=100, blank=True, default='')
    utm_campaign = models.CharField(max_length=100, blank=True, default='', db_index=True)
    utm_content = models.CharField(max_length=100, blank=True, default='')
    utm_term = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.visitor_id} ({self.started:%d/%m/%Y %H:%M})"

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
    acquired_at = models.DateTimeField(default=timezone.now)
    # Exposé dans la vitrine du profil public (objets de collection, 3 au plus).
    showcased = models.BooleanField("En vitrine", default=False)

    def __str__(self):
        return self.item.name

    class Meta:
        verbose_name = 'Inventaire utilisateur'
        verbose_name_plural = 'Inventaires utilisateurs'
        ordering = ['item']
        constraints = [
            models.UniqueConstraint(fields=['user', 'item'], name='unique_user_inventory_item'),
        ]


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

class UtmLink(models.Model):
    """Lien de campagne (paramètres UTM) créé depuis le panel."""

    name = models.CharField("Nom", max_length=120)
    destination = models.CharField("Page de destination", max_length=255, default='/')
    source = models.CharField("Source (utm_source)", max_length=100)
    medium = models.CharField("Support (utm_medium)", max_length=100)
    campaign = models.CharField("Campagne (utm_campaign)", max_length=100)
    content = models.CharField("Contenu (utm_content)", max_length=100, blank=True, default='')
    term = models.CharField("Terme (utm_term)", max_length=100, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='utm_links')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name

    def query_params(self):
        params = {'utm_source': self.source, 'utm_medium': self.medium, 'utm_campaign': self.campaign}
        if self.content:
            params['utm_content'] = self.content
        if self.term:
            params['utm_term'] = self.term
        return params

    def visits(self):
        """Visites arrivées par ce lien."""
        visits = Visit.objects.filter(utm_source=self.source, utm_medium=self.medium,
                                      utm_campaign=self.campaign)
        if self.content:
            visits = visits.filter(utm_content=self.content)
        if self.term:
            visits = visits.filter(utm_term=self.term)
        return visits


class StaffReward(models.Model):
    """Récompense attribuée à la main par l'équipe (concours, événement…)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staff_rewards')
    given_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='staff_rewards_given')
    reason = models.CharField("Motif", max_length=150)
    experience = models.PositiveIntegerField("XP", default=0)
    gold = models.PositiveIntegerField("Or", default=0)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='staff_rewards')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Récompense du staff'
        verbose_name_plural = 'Récompenses du staff'
        ordering = ['-created']

    def __str__(self):
        return f"{self.user} - {self.reason}"
