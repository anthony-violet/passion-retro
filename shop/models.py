from datetime import timedelta
from functools import lru_cache

from django.contrib.staticfiles import finders

from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

# Un objet est « nouveau » pendant ce nombre de jours après sa mise en vente.
NEW_ITEM_DAYS = 14


@lru_cache(maxsize=None)
def _builtin_visual(slug):
    path = f'shop/items/{slug}.svg'
    return path if slug and finders.find(path) else ''


class ItemQuerySet(models.QuerySet):
    def on_sale(self, now=None):
        """Objets actifs dont la période de vente est en cours (stock épuisé compris)."""
        now = now or timezone.now()
        return self.filter(
            is_active=True, category__is_active=True,
        ).filter(
            Q(available_from__isnull=True) | Q(available_from__lte=now),
            Q(available_until__isnull=True) | Q(available_until__gt=now),
        )


class Item(models.Model):
    KIND_FRAME = 'frame'
    KIND_USERNAME = 'username'
    KIND_THEME = 'theme'
    KIND_CONSUMABLE = 'consumable'
    KIND_COLLECTIBLE = 'collectible'
    KIND_CHOICES = [
        (KIND_FRAME, "Cadre d'avatar"),
        (KIND_USERNAME, 'Décoration de pseudo'),
        (KIND_THEME, 'Thème'),
        (KIND_CONSUMABLE, 'Consommable'),
        (KIND_COLLECTIBLE, 'Objet de collection'),
    ]
    # Type d'objet -> champ du membre où il est équipé.
    EQUIP_FIELDS = {
        KIND_FRAME: 'border_avatar',
        KIND_USERNAME: 'username_decoration',
        KIND_THEME: 'theme',
    }

    RARITY_COMMON = 'common'
    RARITY_RARE = 'rare'
    RARITY_EPIC = 'epic'
    RARITY_LEGENDARY = 'legendary'
    RARITY_CHOICES = [
        (RARITY_COMMON, 'Commun'),
        (RARITY_RARE, 'Rare'),
        (RARITY_EPIC, 'Épique'),
        (RARITY_LEGENDARY, 'Légendaire'),
    ]
    RARITY_ORDER = {code: index for index, (code, _) in enumerate(RARITY_CHOICES)}

    EFFECT_NONE = ''
    EFFECT_XP_BOOST = 'xp_boost'
    EFFECT_CHOICES = [
        (EFFECT_NONE, 'Aucun'),
        (EFFECT_XP_BOOST, "Boost d'XP x2"),
    ]

    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='items')
    name = models.CharField("Nom", max_length=100)
    description = models.TextField(blank=True)
    kind = models.CharField("Type", max_length=20, choices=KIND_CHOICES, default=KIND_COLLECTIBLE)
    css_class = models.CharField(
        "Classe CSS", max_length=50, blank=True,
        help_text="Classe du cadre ou de la décoration, ou code du thème. Vide = nom de l'objet en slug.",
    )
    rarity = models.CharField("Rareté", max_length=20, choices=RARITY_CHOICES, default=RARITY_COMMON)
    price = models.PositiveIntegerField("Prix (or)", default=0)
    image = models.ImageField(upload_to='shop/items/', blank=True)
    is_active = models.BooleanField(default=True)

    stock = models.PositiveIntegerField("Stock restant", null=True, blank=True,
                                        help_text="Vide = illimité.")
    available_from = models.DateTimeField("En vente à partir du", null=True, blank=True)
    available_until = models.DateTimeField("En vente jusqu'au", null=True, blank=True)

    discount_percent = models.PositiveSmallIntegerField(
        "Réduction (%)", default=0, validators=[MaxValueValidator(90)],
    )
    discount_from = models.DateTimeField("Promo à partir du", null=True, blank=True)
    discount_until = models.DateTimeField("Promo jusqu'au", null=True, blank=True)

    effect = models.CharField("Effet", max_length=20, choices=EFFECT_CHOICES, blank=True, default=EFFECT_NONE)
    effect_hours = models.PositiveSmallIntegerField("Durée de l'effet (heures)", default=24)

    created_at = models.DateTimeField(default=timezone.now)

    objects = ItemQuerySet.as_manager()

    class Meta:
        ordering = ['category', 'price', 'name']

    def __str__(self):
        return self.name

    # --- Identité visuelle -------------------------------------------------
    @property
    def slug(self):
        """Valeur stockée sur le membre quand l'objet est équipé."""
        return self.css_class or slugify(self.name)

    @property
    def builtin_visual(self):
        """Illustration versionnée ``static/shop/items/<slug>.svg``, utilisée quand l'objet n'a pas d'image."""
        return _builtin_visual(self.slug)

    @property
    def visual_url(self):
        """Image envoyée depuis le panel, sinon illustration versionnée, sinon ''."""
        if self.image:
            return self.image.url
        if self.builtin_visual:
            from django.templatetags.static import static
            return static(self.builtin_visual)
        return ''

    @property
    def rarity_rank(self):
        return self.RARITY_ORDER.get(self.rarity, 0)

    # --- Comportement ------------------------------------------------------
    @property
    def is_equippable(self):
        return self.kind in self.EQUIP_FIELDS

    @property
    def equip_field(self):
        return self.EQUIP_FIELDS.get(self.kind)

    @property
    def is_stackable(self):
        """Un consommable s'achète plusieurs fois ; le reste est unique."""
        return self.kind == self.KIND_CONSUMABLE

    def is_equipped_by(self, user):
        field = self.equip_field
        return bool(field) and getattr(user, field, None) == self.slug

    # --- Disponibilité -----------------------------------------------------
    def is_on_sale(self, now=None):
        now = now or timezone.now()
        if not (self.is_active and self.category.is_active):
            return False
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now >= self.available_until:
            return False
        return True

    @property
    def is_sold_out(self):
        return self.stock is not None and self.stock <= 0

    def is_available(self, now=None):
        return self.is_on_sale(now) and not self.is_sold_out

    @property
    def is_limited(self):
        return self.stock is not None or self.available_until is not None

    @property
    def is_new(self):
        return self.created_at and timezone.now() - self.created_at < timedelta(days=NEW_ITEM_DAYS)

    # --- Prix --------------------------------------------------------------
    def has_discount(self, now=None):
        if not self.discount_percent:
            return False
        now = now or timezone.now()
        if self.discount_from and now < self.discount_from:
            return False
        if self.discount_until and now >= self.discount_until:
            return False
        return True

    def current_price(self, now=None):
        if not self.has_discount(now):
            return self.price
        return self.price * (100 - min(self.discount_percent, 90)) // 100

    @property
    def sale_price(self):
        return self.current_price()

    @property
    def on_discount(self):
        return self.has_discount()


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='items_categories/', blank=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['position', 'name']

    def __str__(self):
        return self.name
