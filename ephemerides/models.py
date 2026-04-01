from django.db import models


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
