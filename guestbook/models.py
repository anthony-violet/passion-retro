from django.db import models

class Guestbook(models.Model):
    id = models.AutoField(primary_key=True)
    author = models.CharField(max_length=50, default='Visiteur')
    content = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    # Empreinte HMAC de l'IP (jamais l'IP en clair), pour limiter le spam.
    ip_hash = models.CharField(max_length=64, blank=True, default='', db_index=True, editable=False)

    def __str__(self):
        return f'Guestbook({self.id}, {self.author}, {self.content}, {self.created})'