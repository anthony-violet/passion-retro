from django.db import models

# Create your models here.
class HistoryVersion(models.Model):
    id = models.AutoField(primary_key=True)
    num_version = models.CharField(max_length=5)
    name = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name