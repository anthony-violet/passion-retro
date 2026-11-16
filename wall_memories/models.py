import os
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def memory_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    return f"wall_memories/{uuid.uuid4().hex}{ext}"


class Console(models.Model):
    """Liste fermée des consoles, gérée depuis le panel."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    release_year = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Console'
        verbose_name_plural = 'Consoles'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:110]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Memory(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_HIDDEN = 'hidden'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_PUBLISHED, 'Publié'),
        (STATUS_REJECTED, 'Refusé'),
        (STATUS_HIDDEN, 'Masqué'),
    ]

    ERA_80S = '80s'
    ERA_90S = '90s'
    ERA_00S = '00s'
    ERA_OTHER = 'other'
    ERA_CHOICES = [
        (ERA_80S, 'Années 80'),
        (ERA_90S, 'Années 90'),
        (ERA_00S, 'Années 2000'),
        (ERA_OTHER, 'Autre époque'),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memories'
    )
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True)
    content = models.TextField()
    question = models.CharField(max_length=200, blank=True)
    consoles = models.ManyToManyField(Console, blank=True, related_name='memories')
    era = models.CharField(max_length=10, choices=ERA_CHOICES, default=ERA_90S)
    year = models.PositiveIntegerField(null=True, blank=True)
    image = models.ImageField(upload_to=memory_image_path, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.TextField(blank=True)

    reactions_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_memories',
    )
    xp_granted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = 'Souvenir'
        verbose_name_plural = 'Souvenirs'
        indexes = [
            models.Index(fields=['status', '-published_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:170] or 'souvenir'
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('wall_memories:detail', args=[self.pk, self.slug])

    @property
    def is_published(self):
        return self.status == self.STATUS_PUBLISHED

    def refresh_counters(self):
        self.reactions_count = self.reactions.count()
        self.comments_count = self.comments.filter(
            status=MemoryComment.STATUS_PUBLISHED
        ).count()
        Memory.objects.filter(pk=self.pk).update(
            reactions_count=self.reactions_count,
            comments_count=self.comments_count,
        )

    def __str__(self):
        return self.title


class MemoryReaction(models.Model):
    LOVE = 'love'
    NOSTALGIA = 'nostalgia'
    SAME = 'same'
    LAUGH = 'laugh'
    TYPE_CHOICES = [
        (LOVE, 'Ça me rappelle tellement de souvenirs'),
        (NOSTALGIA, 'Quelle époque !'),
        (SAME, "J'ai vécu la même chose"),
        (LAUGH, "Ça m'est arrivé aussi !"),
    ]
    EMOJIS = {
        LOVE: '❤️',
        NOSTALGIA: '🥹',
        SAME: '🎮',
        LAUGH: '😂',
    }

    memory = models.ForeignKey(Memory, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memory_reactions'
    )
    type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Réaction'
        verbose_name_plural = 'Réactions'
        constraints = [
            models.UniqueConstraint(
                fields=['memory', 'user', 'type'], name='unique_memory_reaction'
            ),
        ]

    @property
    def emoji(self):
        return self.EMOJIS.get(self.type, '')

    def __str__(self):
        return f"{self.user} {self.emoji} {self.memory}"


class MemoryComment(models.Model):
    STATUS_PUBLISHED = 'published'
    STATUS_HIDDEN = 'hidden'
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, 'Publié'),
        (STATUS_HIDDEN, 'Masqué'),
    ]

    memory = models.ForeignKey(Memory, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memory_comments'
    )
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    xp_granted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Commentaire'
        verbose_name_plural = 'Commentaires'

    def __str__(self):
        return f"{self.author} sur {self.memory}"


class MemoryFavorite(models.Model):
    memory = models.ForeignKey(Memory, on_delete=models.CASCADE, related_name='favorites')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memory_favorites'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Favori'
        verbose_name_plural = 'Favoris'
        constraints = [
            models.UniqueConstraint(fields=['memory', 'user'], name='unique_memory_favorite'),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.memory}"


class MemoryFeature(models.Model):
    """Mise en avant éditoriale (exploitée en phase 2)."""

    TYPE_WEEK = 'week'
    TYPE_DAY = 'day'
    TYPE_CHOICES = [
        (TYPE_WEEK, 'Souvenir de la semaine'),
        (TYPE_DAY, 'Souvenir du jour'),
    ]

    memory = models.ForeignKey(Memory, on_delete=models.CASCADE, related_name='features')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_WEEK)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    editorial_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Mise en avant'
        verbose_name_plural = 'Mises en avant'

    def __str__(self):
        return f"{self.get_type_display()} — {self.memory}"
