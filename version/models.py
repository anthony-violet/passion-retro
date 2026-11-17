from django.db import models


class HistoryVersion(models.Model):
    id = models.AutoField(primary_key=True)
    num_version = models.CharField(max_length=5)
    name = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(
        upload_to='versions/', blank=True, null=True,
        verbose_name="Capture d'écran",
        help_text="Facultative : illustre la version dans l'historique.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Version'
        verbose_name_plural = 'Versions'

    def __str__(self):
        return self.name

    @classmethod
    def latest(cls):
        """Dernière version créée (affichée dans le footer)."""
        return cls.objects.order_by('-created_at', '-id').first()
