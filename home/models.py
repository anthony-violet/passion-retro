from datetime import date

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models


MONTH_CHOICES = [
    (1, "janvier"), (2, "février"), (3, "mars"), (4, "avril"), (5, "mai"), (6, "juin"),
    (7, "juillet"), (8, "août"), (9, "septembre"), (10, "octobre"), (11, "novembre"), (12, "décembre"),
]
DAY_CHOICES = [(d, str(d)) for d in range(1, 32)]


class ChristmasSettings(models.Model):
    """Réglages du décor de Noël (une seule ligne, éditée depuis le panel).

    Les dates sont en jour/mois et se répètent chaque année ; une période peut
    passer le cap du 31 décembre (ex. 1er décembre → 10 janvier).
    """

    MODE_AUTO = "auto"
    MODE_ON = "on"
    MODE_OFF = "off"
    MODE_CHOICES = [
        (MODE_AUTO, "Automatique (selon les dates)"),
        (MODE_ON, "Toujours activé"),
        (MODE_OFF, "Désactivé"),
    ]
    CACHE_KEY = "christmas_settings"

    mode = models.CharField("Mode", max_length=10, choices=MODE_CHOICES, default=MODE_AUTO)
    start_day = models.PositiveSmallIntegerField("Jour de début", choices=DAY_CHOICES, default=1)
    start_month = models.PositiveSmallIntegerField("Mois de début", choices=MONTH_CHOICES, default=12)
    end_day = models.PositiveSmallIntegerField("Jour de fin", choices=DAY_CHOICES, default=10)
    end_month = models.PositiveSmallIntegerField("Mois de fin", choices=MONTH_CHOICES, default=1)

    class Meta:
        verbose_name = "Réglages du décor de Noël"
        verbose_name_plural = "Réglages du décor de Noël"

    def __str__(self):
        return "Décor de Noël"

    def clean(self):
        # 2000 est bissextile : le 29 février est accepté, le 31 février non.
        for label, day, month in (
            ("start_day", self.start_day, self.start_month),
            ("end_day", self.end_day, self.end_month),
        ):
            try:
                date(2000, month, day)
            except (TypeError, ValueError):
                raise ValidationError({label: f"Le {day}/{month} n'existe pas."})

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls):
        settings_obj = cache.get(cls.CACHE_KEY)
        if settings_obj is None:
            settings_obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, settings_obj, 60)
        return settings_obj

    def includes(self, day: date) -> bool:
        """La date tombe-t-elle dans la période (bornes incluses) ?"""
        current = (day.month, day.day)
        start = (self.start_month, self.start_day)
        end = (self.end_month, self.end_day)
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
