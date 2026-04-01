from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Ephemeride(models.Model):
    CATEGORY_CHOICES = [
        ('jeu', '🎮 Jeu vidéo'),
        ('console', '🕹️ Console'),
        ('film', '🎬 Film'),
        ('serie', '📺 Série'),
        ('musique', '🎵 Musique'),
        ('livre', '📖 Livre'),
        ('evenement', '📅 Événement'),
        ('autre', '✨ Autre'),
    ]

    day = models.PositiveSmallIntegerField(verbose_name="Jour")
    month = models.PositiveSmallIntegerField(verbose_name="Mois")
    year = models.IntegerField(verbose_name="Année")
    title = models.CharField(max_length=255, verbose_name="Titre")
    content = models.TextField(verbose_name="Description", blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='autre', verbose_name="Catégorie")

    class Meta:
        app_label = 'ephemerides'
        ordering = ['-year']
        verbose_name = "Éphéméride"
        verbose_name_plural = "Éphémérides"

    def __str__(self):
        return f"{self.day:02d}/{self.month:02d}/{self.year} — {self.title}"

    def get_category_display_icon(self):
        icons = dict(self.CATEGORY_CHOICES)
        return icons.get(self.category, '✨')


class ContributedEphemeride(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_APPROVED, 'Approuvée'),
        (STATUS_REJECTED, 'Rejetée'),
    ]

    CATEGORY_CHOICES = Ephemeride.CATEGORY_CHOICES

    day = models.PositiveSmallIntegerField(verbose_name="Jour")
    month = models.PositiveSmallIntegerField(verbose_name="Mois")
    year = models.IntegerField(verbose_name="Année")
    title = models.CharField(max_length=255, verbose_name="Titre")
    content = models.TextField(verbose_name="Description", blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='autre', verbose_name="Catégorie")
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Contributeur")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Révision le")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_ephemerides', verbose_name="Révision par")
    rejection_reason = models.TextField(verbose_name="Raison du rejet", blank=True)

    class Meta:
        app_label = 'ephemerides'
        ordering = ['-created_at']
        verbose_name = "Contribution d'éphéméride"
        verbose_name_plural = "Contributions d'éphémérides"

    def __str__(self):
        return f"{self.title} (par {self.user})"

    def get_category_display_icon(self):
        icons = dict(self.CATEGORY_CHOICES)
        return icons.get(self.category, '✨')
