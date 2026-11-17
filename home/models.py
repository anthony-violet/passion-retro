from datetime import date

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models


class SeasonalEvent(models.Model):
    """Période d'affichage d'un décor thématique ou d'une édition spéciale.

    Une ligne par décor (Noël, éditions Vice City et Doomsday…), éditée depuis le panel.
    - « Se répète chaque année » : seuls le jour et le mois comptent (l'année est
      ignorée) et la période peut passer le cap du 31 décembre.
    - Sinon, la période est fixe, du jour de début au jour de fin inclus.
    """

    CHRISTMAS = "christmas"
    VICECITY = "vicecity"
    DOOMSDAY = "doomsday"
    KEY_CHOICES = [
        (CHRISTMAS, "Décor de Noël"),
        (VICECITY, "Édition spéciale Vice City"),
        (DOOMSDAY, "Édition spéciale Doomsday"),
    ]

    MODE_AUTO = "auto"
    MODE_ON = "on"
    MODE_OFF = "off"
    MODE_CHOICES = [
        (MODE_AUTO, "Automatique (selon les dates)"),
        (MODE_ON, "Toujours activé"),
        (MODE_OFF, "Désactivé"),
    ]

    CACHE_KEY = "seasonal_events"
    CACHE_TIMEOUT = 60

    key = models.CharField("Décor", max_length=30, choices=KEY_CHOICES, unique=True)
    mode = models.CharField("Mode", max_length=10, choices=MODE_CHOICES, default=MODE_OFF)
    start_date = models.DateField("Début", null=True, blank=True)
    end_date = models.DateField("Fin (incluse)", null=True, blank=True)
    repeat_yearly = models.BooleanField("Se répète chaque année", default=False)

    class Meta:
        verbose_name = "Décor thématique"
        verbose_name_plural = "Décors thématiques"
        ordering = ["key"]

    def __str__(self):
        return self.get_key_display()

    def clean(self):
        if bool(self.start_date) != bool(self.end_date):
            raise ValidationError("Renseigne la date de début et la date de fin, ou aucune des deux.")
        if self.mode == self.MODE_AUTO and not self.start_date:
            raise ValidationError({"start_date": "Le mode automatique a besoin d'une période."})
        if self.start_date and not self.repeat_yearly and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin doit être après le début."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        cache.delete(self.CACHE_KEY)
        return result

    @classmethod
    def all_by_key(cls):
        """Tous les décors, indexés par clé ; créés à la volée s'ils manquent."""
        events = cache.get(cls.CACHE_KEY)
        if events is None:
            events = {event.key: event for event in cls.objects.all()}
            for key, _label in cls.KEY_CHOICES:
                if key not in events:
                    events[key], _ = cls.objects.get_or_create(key=key)
            cache.set(cls.CACHE_KEY, events, cls.CACHE_TIMEOUT)
        return events

    @classmethod
    def get(cls, key):
        return cls.all_by_key()[key]

    def includes(self, day: date) -> bool:
        """La date tombe-t-elle dans la période (bornes incluses) ?"""
        if not self.start_date or not self.end_date:
            return False
        if not self.repeat_yearly:
            return self.start_date <= day <= self.end_date
        current = (day.month, day.day)
        start = (self.start_date.month, self.start_date.day)
        end = (self.end_date.month, self.end_date.day)
        if start <= end:
            return start <= current <= end
        # La période passe le cap du 31 décembre.
        return current >= start or current <= end

    def is_active(self, day: date) -> bool:
        if self.mode == self.MODE_ON:
            return True
        if self.mode == self.MODE_OFF:
            return False
        return self.includes(day)
