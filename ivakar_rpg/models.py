"""Ivakar, le RPG textuel de Passion Rétro.

Le monde (lieux, scènes, choix, monstres, objets, quêtes) est écrit en base par
l'équipe, depuis l'admin. Les règles du jeu vivent dans ``ivakar_rpg.engine``.

Le RPG a ses propres niveaux et sa propre monnaie (les écus). Il est relié au
site par deux ponts seulement :
- les paliers de niveau (``LevelReward``) débloquent un titre, un objet de la
  boutique du site ou de l'XP du site ;
- le bureau de change convertit l'or du site en écus, jamais l'inverse.
"""
from functools import lru_cache

from django.contrib.staticfiles import finders
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.templatetags.static import static

from users.models import User

COIN_NAME = "écu"
COIN_NAME_PLURAL = "écus"

# Seuils de difficulté validés (règles d'Ivakar, III).
DIFFICULTY_EASY = 10
DIFFICULTY_MEDIUM = 13
DIFFICULTY_HARD = 16
DIFFICULTY_CHOICES = [
    (DIFFICULTY_EASY, "Facile (10)"),
    (DIFFICULTY_MEDIUM, "Moyenne (13)"),
    (DIFFICULTY_HARD, "Difficile (16)"),
]
# Coordonnées sur la carte : de 0 à 1000 sur chaque axe (millièmes de la largeur / hauteur).
MAP_SIZE = 1000
VISUAL_EXTENSIONS = ('svg', 'webp', 'png', 'jpg')


@lru_cache(maxsize=None)
def builtin_visual(folder, slug):
    """Illustration versionnée ``static/ivakar/<folder>/<slug>.<ext>`` ou ``''``."""
    if not slug:
        return ''
    for ext in VISUAL_EXTENSIONS:
        path = f'ivakar/{folder}/{slug}.{ext}'
        if finders.find(path):
            return path
    return ''


class Illustrated(models.Model):
    """Image envoyée depuis le panel, sinon illustration versionnée dans ``static/ivakar/``."""

    VISUAL_FOLDER = ''

    image = models.ImageField("Illustration", upload_to='ivakar/', blank=True,
                              help_text="Remplace l'illustration fournie. Format paysage conseillé.")

    class Meta:
        abstract = True

    @property
    def has_uploaded_image(self):
        try:
            return bool(self.image) and self.image.storage.exists(self.image.name)
        except Exception:
            return False

    @property
    def visual_url(self):
        if self.has_uploaded_image:
            return self.image.url
        path = builtin_visual(self.VISUAL_FOLDER, getattr(self, 'slug', ''))
        return static(path) if path else ''


# Valeurs d'une caractéristique au niveau 1 (règles, IV).
START_STAT_MIN = 1
START_STAT_MAX = 20


# ---------------------------------------------------------------------------
# Personnage
# ---------------------------------------------------------------------------
class Characteristic(models.Model):
    """Force, Agilité, Esprit, Vitalité… ``code`` est utilisé par le moteur."""

    code = models.SlugField("Code", max_length=30, unique=True)
    name = models.CharField("Nom", max_length=50)
    description = models.TextField(blank=True)
    is_hidden = models.BooleanField("Cachée", default=False)
    order = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Caractéristique"

    def __str__(self):
        return self.name


class Origin(models.Model):
    """Choix initial du personnage : fixe ses caractéristiques de départ, sans l'enfermer dans une classe."""

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField("Nom", max_length=60)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField("Ordre", default=0)
    is_active = models.BooleanField("Proposée à la création", default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Origine"

    def __str__(self):
        return self.name

    @property
    def values_total(self):
        return sum(row.value for row in self.values.all())


class OriginCharacteristic(models.Model):
    origin = models.ForeignKey(Origin, on_delete=models.CASCADE, related_name='values')
    characteristic = models.ForeignKey(Characteristic, verbose_name="Caractéristique", on_delete=models.CASCADE, related_name='+')
    value = models.PositiveSmallIntegerField(
        "Valeur de départ", default=10,
        validators=[MinValueValidator(START_STAT_MIN), MaxValueValidator(START_STAT_MAX)],
    )

    class Meta:
        ordering = ['characteristic__order']
        constraints = [
            models.UniqueConstraint(fields=['origin', 'characteristic'], name='unique_origin_characteristic'),
        ]


class Character(models.Model):
    STATE_OK = 'ok'
    STATE_KO = 'ko'
    STATE_CHOICES = [(STATE_OK, 'Conscient'), (STATE_KO, 'Inconscient (KO)')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="character")
    name = models.CharField("Nom du héros", max_length=40)
    origin = models.ForeignKey(Origin, verbose_name="Origine", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='+')
    # État physique, distinct des blessures (règles, V).
    state = models.CharField("État", max_length=10, choices=STATE_CHOICES, default=STATE_OK)
    level = models.PositiveIntegerField("Niveau", default=1)
    xp = models.PositiveIntegerField("Expérience", default=0)
    coins = models.PositiveIntegerField(COIN_NAME_PLURAL.capitalize(), default=0)
    hp = models.PositiveIntegerField("Points de vie", default=1)
    unspent_points = models.PositiveSmallIntegerField("Points à répartir", default=0)
    location = models.ForeignKey(
        'Location', verbose_name="Lieu", on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    scene = models.ForeignKey(
        'Scene', verbose_name="Scène en cours", on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    # Marqueurs d'histoire posés par les choix (``Outcome.set_flag``) et
    # scènes uniques déjà vues (``scene:<slug>``).
    flags = models.JSONField(default=list, blank=True)
    # Lieux déjà visités (identifiants) : la carte n'en montre que ceux-là et leurs voisins.
    visited = models.JSONField(default=list, blank=True)
    # Derniers événements racontés au joueur (le plus récent en dernier).
    log = models.JSONField(default=list, blank=True)
    show_title = models.BooleanField("Afficher mon titre sur le site", default=True)
    victories = models.PositiveIntegerField(default=0)
    knockouts = models.PositiveIntegerField("KO subis", default=0)
    duel_wins = models.PositiveIntegerField("Duels gagnés", default=0)
    duel_losses = models.PositiveIntegerField("Duels perdus", default=0)
    # Dernière activité dans le jeu : sert à montrer qui est présent dans un lieu.
    last_seen_at = models.DateTimeField("Vu pour la dernière fois", null=True, blank=True)
    # Voyages effectués : sert à rythmer le risque d'aggravation lié au temps sans soins.
    travel_count = models.PositiveIntegerField("Voyages", default=0)
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Personnage"

    def __str__(self):
        return f"{self.name} ({self.user})"

    def has_flag(self, flag):
        return bool(flag) and flag in (self.flags or [])

    @property
    def is_ko(self):
        return self.state == self.STATE_KO


class Wound(models.Model):
    """Blessure : légère, modérée ou grave. Elle peut s'aggraver, sans que ce soit systématique."""

    SEVERITY_LIGHT = 1
    SEVERITY_MODERATE = 2
    SEVERITY_SEVERE = 3
    SEVERITY_CHOICES = [(SEVERITY_LIGHT, 'Légère'), (SEVERITY_MODERATE, 'Modérée'), (SEVERITY_SEVERE, 'Grave')]

    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='wounds')
    severity = models.PositiveSmallIntegerField("Gravité", choices=SEVERITY_CHOICES, default=SEVERITY_LIGHT)
    label = models.CharField("Description", max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-severity', 'created_at']
        verbose_name = "Blessure"

    def __str__(self):
        return f"{self.get_severity_display()} — {self.label}"


class CharacterCharacteristic(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name="characteristics")
    characteristic = models.ForeignKey(Characteristic, on_delete=models.CASCADE, related_name="characters")
    value = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['characteristic__order']
        constraints = [
            models.UniqueConstraint(fields=["character", "characteristic"],
                                    name="unique_character_characteristic"),
        ]


class Inventory(models.Model):
    character = models.OneToOneField(Character, on_delete=models.CASCADE, related_name="inventory")


class Item(Illustrated):
    VISUAL_FOLDER = 'objets'

    KIND_WEAPON = 'weapon'
    KIND_ARMOR = 'armor'
    KIND_CONSUMABLE = 'consumable'
    KIND_QUEST = 'quest'
    KIND_MISC = 'misc'
    KIND_CHOICES = [
        (KIND_WEAPON, 'Arme'),
        (KIND_ARMOR, 'Armure'),
        (KIND_CONSUMABLE, 'Consommable'),
        (KIND_QUEST, 'Objet de quête'),
        (KIND_MISC, 'Divers'),
    ]
    EQUIPPABLE = (KIND_WEAPON, KIND_ARMOR)

    RARITY_CHOICES = [
        ('common', 'Commun'),
        ('rare', 'Rare'),
        ('epic', 'Épique'),
        ('legendary', 'Légendaire'),
    ]

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField("Nom", max_length=50)
    description = models.TextField(blank=True)
    kind = models.CharField("Type", max_length=20, choices=KIND_CHOICES, default=KIND_MISC)
    rarity = models.CharField("Rareté", max_length=20, choices=RARITY_CHOICES, default='common')
    price = models.PositiveIntegerField("Prix (écus)", default=0)
    attack_bonus = models.IntegerField("Bonus de dégâts", default=0)
    defense_bonus = models.IntegerField("Armure (dégâts absorbés)", default=0)
    hp_bonus = models.IntegerField("Bonus de PV max", default=0)
    heal = models.PositiveIntegerField("Soin (consommable)", default=0)
    sold_at = models.ManyToManyField(
        'Location', verbose_name="Vendu chez le marchand de", blank=True, related_name='wares',
    )

    class Meta:
        ordering = ['kind', 'price', 'name']
        verbose_name = "Objet"

    def __str__(self):
        return self.name

    @property
    def is_equippable(self):
        return self.kind in self.EQUIPPABLE

    @property
    def is_sellable(self):
        return self.kind != self.KIND_QUEST and self.price > 0

    @property
    def sell_price(self):
        return self.price // 2


class InventoryItem(models.Model):
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField("Équipé", default=False)

    class Meta:
        ordering = ['item__kind', 'item__name']
        constraints = [
            models.UniqueConstraint(fields=["inventory", "item"], name="unique_inventory_item"),
        ]


# ---------------------------------------------------------------------------
# Monde
# ---------------------------------------------------------------------------
class Location(Illustrated):
    VISUAL_FOLDER = 'lieux'

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField("Nom", max_length=80)
    description = models.TextField("Description (BBCode)", blank=True)
    is_start = models.BooleanField("Lieu de départ", default=False,
                                   help_text="Où naissent les héros et où ils se réveillent après une défaite.")
    is_safe = models.BooleanField("Lieu sûr", default=False, help_text="Aucun monstre n'y rôde.")
    has_inn = models.BooleanField("Auberge", default=False)
    inn_price = models.PositiveIntegerField("Prix de la nuit (écus)", default=5)
    has_merchant = models.BooleanField("Marchand", default=False)
    recommended_level = models.PositiveSmallIntegerField("Niveau conseillé", default=1)
    calm_weight = models.PositiveSmallIntegerField(
        "Poids « rien à signaler »", default=2,
        help_text="Chance relative qu'une exploration ne donne rien.",
    )
    order = models.PositiveSmallIntegerField("Ordre", default=0)
    map_x = models.PositiveSmallIntegerField("Carte : position horizontale", null=True, blank=True,
                                             validators=[MaxValueValidator(MAP_SIZE)],
                                             help_text="0 = bord gauche, 1000 = bord droit. Vide = absent de la carte.")
    map_y = models.PositiveSmallIntegerField("Carte : position verticale", null=True, blank=True,
                                             validators=[MaxValueValidator(MAP_SIZE)],
                                             help_text="0 = haut, 1000 = bas.")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Lieu"

    def __str__(self):
        return self.name


class LocationExit(models.Model):
    from_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='exits')
    to_location = models.ForeignKey(Location, verbose_name="Vers", on_delete=models.CASCADE, related_name='+')
    label = models.CharField("Libellé", max_length=80, blank=True,
                             help_text="Ex. « Prendre le sentier vers la forêt ». Vide = nom du lieu.")
    required_level = models.PositiveSmallIntegerField("Niveau requis", default=0)
    required_item = models.ForeignKey(Item, verbose_name="Objet requis", on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='+')
    required_flag = models.CharField("Marqueur requis", max_length=60, blank=True)
    locked_text = models.CharField("Message si bloqué", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Sortie"

    def __str__(self):
        return self.label or f"Vers {self.to_location}"


class Monster(Illustrated):
    VISUAL_FOLDER = 'monstres'

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField("Nom", max_length=60)
    description = models.TextField(blank=True)
    level = models.PositiveSmallIntegerField("Niveau", default=1)
    hp = models.PositiveIntegerField("PV", default=10)
    # Le monstre est décrit par les seuils que le héros doit atteindre (2D6 + ⌊Dextérité ÷ 3⌋).
    hit_difficulty = models.PositiveSmallIntegerField("Seuil pour le toucher", choices=DIFFICULTY_CHOICES,
                                                      default=DIFFICULTY_EASY)
    dodge_difficulty = models.PositiveSmallIntegerField("Seuil pour esquiver ses attaques",
                                                        choices=DIFFICULTY_CHOICES, default=DIFFICULTY_EASY)
    flee_difficulty = models.PositiveSmallIntegerField("Seuil pour le fuir", choices=DIFFICULTY_CHOICES,
                                                       default=DIFFICULTY_MEDIUM)
    damage_min = models.PositiveSmallIntegerField("Dégâts min", default=1)
    damage_max = models.PositiveSmallIntegerField("Dégâts max", default=4)
    armor = models.PositiveSmallIntegerField("Armure", default=0)
    xp = models.PositiveIntegerField("XP gagnée", default=10)
    coins_min = models.PositiveIntegerField("Écus min", default=0)
    coins_max = models.PositiveIntegerField("Écus max", default=0)
    is_boss = models.BooleanField("Boss (fuite impossible)", default=False)

    class Meta:
        ordering = ['level', 'name']
        verbose_name = "Monstre"

    def __str__(self):
        return self.name

    @property
    def damage_range(self):
        return f"{self.damage_min}–{self.damage_max}"


class MonsterLoot(models.Model):
    monster = models.ForeignKey(Monster, on_delete=models.CASCADE, related_name='loot')
    item = models.ForeignKey(Item, verbose_name="Objet", on_delete=models.CASCADE)
    chance = models.PositiveSmallIntegerField("Chance (%)", default=25)

    class Meta:
        verbose_name = "Butin"


class LocationEncounter(models.Model):
    """Monstre qui peut surgir quand on explore un lieu."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='encounters')
    monster = models.ForeignKey(Monster, verbose_name="Monstre", on_delete=models.CASCADE, related_name='+')
    weight = models.PositiveSmallIntegerField("Poids", default=1)

    class Meta:
        verbose_name = "Rencontre"


class Quest(models.Model):
    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField("Titre", max_length=100)
    summary = models.TextField("Résumé", blank=True)
    objective = models.CharField("Objectif affiché", max_length=200, blank=True)
    reward_xp = models.PositiveIntegerField("XP", default=0)
    reward_coins = models.PositiveIntegerField("Écus", default=0)
    reward_item = models.ForeignKey(Item, verbose_name="Objet", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='+')
    order = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = "Quête"

    def __str__(self):
        return self.title


class CharacterQuest(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [(STATUS_ACTIVE, 'En cours'), (STATUS_DONE, 'Terminée')]

    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='quests')
    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name='+')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['status', '-started_at']
        constraints = [
            models.UniqueConstraint(fields=['character', 'quest'], name='unique_character_quest'),
        ]


# ---------------------------------------------------------------------------
# Histoire : scènes, choix et conséquences
# ---------------------------------------------------------------------------
class Scene(Illustrated):
    VISUAL_FOLDER = 'scenes'

    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField("Titre", max_length=100)
    text = models.TextField("Texte (BBCode)")
    location = models.ForeignKey(Location, verbose_name="Lieu", on_delete=models.CASCADE,
                                 null=True, blank=True, related_name='scenes')
    explore_weight = models.PositiveSmallIntegerField(
        "Poids en exploration", default=0,
        help_text="0 = la scène n'arrive que par un choix. Sinon, chance relative d'y tomber en explorant.",
    )
    once = models.BooleanField("Une seule fois par héros", default=False)
    min_level = models.PositiveSmallIntegerField("Niveau minimum", default=0)
    required_flag = models.CharField("Marqueur requis", max_length=60, blank=True)
    forbidden_flag = models.CharField("Marqueur interdit", max_length=60, blank=True)

    class Meta:
        ordering = ['location', 'title']
        verbose_name = "Scène"

    def __str__(self):
        return self.title

    @property
    def seen_flag(self):
        return f"scene:{self.slug}"

    @property
    def visual_url(self):
        """Sa propre illustration, sinon celle de son lieu."""
        own = super().visual_url
        if own or not self.location_id:
            return own
        return self.location.visual_url


class Choice(models.Model):
    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name='choices')
    label = models.CharField("Libellé", max_length=150)
    order = models.PositiveSmallIntegerField("Ordre", default=0)
    # Conditions pour pouvoir choisir.
    required_level = models.PositiveSmallIntegerField("Niveau requis", default=0)
    required_item = models.ForeignKey(Item, verbose_name="Objet requis", on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='+')
    required_coins = models.PositiveIntegerField("Écus requis", default=0)
    required_flag = models.CharField("Marqueur requis", max_length=60, blank=True)
    forbidden_flag = models.CharField("Marqueur interdit", max_length=60, blank=True)
    hide_if_unavailable = models.BooleanField("Masquer si indisponible", default=False)
    # Test facultatif : 2D6 + ⌊caractéristique ÷ 3⌋ >= seuil.
    test_characteristic = models.ForeignKey(Characteristic, verbose_name="Test de",
                                            on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='+')
    test_difficulty = models.PositiveSmallIntegerField("Difficulté", choices=DIFFICULTY_CHOICES,
                                                       default=DIFFICULTY_MEDIUM)

    class Meta:
        ordering = ['scene', 'order', 'id']
        verbose_name = "Choix"
        verbose_name_plural = "Choix"

    def __str__(self):
        return f"{self.scene} → {self.label}"


class Outcome(models.Model):
    """Conséquence d'un choix : en cas de réussite (ou sans test) ou d'échec."""

    RESULT_SUCCESS = 'success'
    RESULT_FAILURE = 'failure'
    RESULT_CHOICES = [(RESULT_SUCCESS, 'Réussite / sans test'), (RESULT_FAILURE, 'Échec du test')]

    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, related_name='outcomes')
    result = models.CharField("Cas", max_length=10, choices=RESULT_CHOICES, default=RESULT_SUCCESS)
    text = models.TextField("Récit (BBCode)", blank=True)
    xp = models.PositiveIntegerField("XP", default=0)
    coins = models.IntegerField("Écus (+/-)", default=0)
    hp = models.IntegerField("PV (+ soin / - dégâts)", default=0)
    wound = models.PositiveSmallIntegerField("Inflige une blessure", choices=[(0, 'Aucune')] + Wound.SEVERITY_CHOICES,
                                             default=0)
    wound_label = models.CharField("Description de la blessure", max_length=120, blank=True)
    strain_wounds = models.BooleanField(
        "Sollicite les blessures", default=False,
        help_text="Risque d'aggravation lié au contexte (seuil = Force × coefficient) pour chaque blessure.",
    )
    give_item = models.ForeignKey(Item, verbose_name="Donne l'objet", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='+')
    take_item = models.ForeignKey(Item, verbose_name="Retire l'objet", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='+')
    set_flag = models.CharField("Pose le marqueur", max_length=60, blank=True)
    start_quest = models.ForeignKey(Quest, verbose_name="Démarre la quête", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='+')
    complete_quest = models.ForeignKey(Quest, verbose_name="Termine la quête", on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='+')
    move_to = models.ForeignKey(Location, verbose_name="Emmène vers", on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    combat = models.ForeignKey(Monster, verbose_name="Déclenche un combat contre", on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='+')
    next_scene = models.ForeignKey(Scene, verbose_name="Scène suivante (après le combat s'il y en a un)",
                                   on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        verbose_name = "Conséquence"
        constraints = [
            models.UniqueConstraint(fields=['choice', 'result'], name='unique_choice_outcome'),
        ]

    def __str__(self):
        return f"{self.choice} [{self.get_result_display()}]"


class Combat(models.Model):
    character = models.OneToOneField(Character, on_delete=models.CASCADE, related_name='combat')
    monster = models.ForeignKey(Monster, verbose_name="Monstre", on_delete=models.CASCADE, related_name='+')
    monster_hp = models.PositiveIntegerField()
    turn = models.PositiveIntegerField(default=1)
    defending = models.BooleanField(default=False)
    log = models.JSONField(default=list, blank=True)
    then_scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    started_at = models.DateTimeField(auto_now_add=True)


# ---------------------------------------------------------------------------
# Ponts avec le site
# ---------------------------------------------------------------------------
class LevelReward(models.Model):
    KIND_TITLE = 'title'
    KIND_SITE_ITEM = 'site_item'
    KIND_SITE_XP = 'site_xp'
    KIND_CHOICES = [
        (KIND_TITLE, 'Titre affiché sur le site'),
        (KIND_SITE_ITEM, 'Objet de la boutique du site (cadre, badge…)'),
        (KIND_SITE_XP, 'XP du site'),
    ]

    level = models.PositiveSmallIntegerField("Niveau RPG")
    kind = models.CharField("Type", max_length=20, choices=KIND_CHOICES)
    label = models.CharField("Libellé / titre", max_length=80)
    description = models.CharField(max_length=200, blank=True)
    shop_item = models.ForeignKey('shop.Item', verbose_name="Objet du site", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='+')
    site_xp = models.PositiveIntegerField("XP du site", default=0)

    class Meta:
        ordering = ['level', 'kind']
        verbose_name = "Récompense de palier"

    def __str__(self):
        return f"Niv. {self.level} — {self.label}"


class CharacterReward(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='rewards')
    reward = models.ForeignKey(LevelReward, on_delete=models.CASCADE, related_name='+')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['character', 'reward'], name='unique_character_reward'),
        ]


class CoinExchange(models.Model):
    """Journal du bureau de change : or du site → écus (jamais l'inverse)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rpg_exchanges')
    gold_spent = models.PositiveIntegerField()
    coins_received = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Change"


class WorldMap(models.Model):
    """Fond de la carte du monde. Sans image envoyée, le parchemin fourni est utilisé."""

    DEFAULT_BACKGROUND = 'ivakar/carte/parchemin.svg'

    image = models.ImageField("Fond de carte", upload_to='ivakar/carte/', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Carte du monde"

    @classmethod
    def current(cls):
        return cls.objects.first() or cls()

    @property
    def has_custom_background(self):
        try:
            return bool(self.image) and self.image.storage.exists(self.image.name)
        except Exception:
            return False

    @property
    def background_url(self):
        try:
            if self.image and self.image.storage.exists(self.image.name):
                return self.image.url
        except Exception:
            pass
        return static(self.DEFAULT_BACKGROUND)


# ---------------------------------------------------------------------------
# Multijoueur : taverne, échanges, duels, événements de serveur
# ---------------------------------------------------------------------------
class LocationMessage(models.Model):
    """Message laissé dans la taverne d'un lieu (visible par les héros présents)."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='messages')
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='messages')
    text = models.CharField("Message", max_length=300)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_hidden = models.BooleanField("Masqué par la modération", default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Message de taverne"

    def __str__(self):
        return f"{self.character.name} @ {self.location} : {self.text[:40]}"


class Trade(models.Model):
    """Proposition d'échange : ce que l'un donne contre ce qu'il demande à l'autre."""

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_DECLINED = 'declined'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_ACCEPTED, 'Accepté'),
        (STATUS_DECLINED, 'Refusé'),
        (STATUS_CANCELLED, 'Annulé'),
        (STATUS_FAILED, 'Impossible'),
    ]

    proposer = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='trades_sent')
    receiver = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='trades_received')
    offer_coins = models.PositiveIntegerField("Écus donnés", default=0)
    request_coins = models.PositiveIntegerField("Écus demandés", default=0)
    message = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Échange"

    def __str__(self):
        return f"{self.proposer.name} → {self.receiver.name} ({self.get_status_display()})"


class TradeLine(models.Model):
    SIDE_OFFER = 'offer'
    SIDE_REQUEST = 'request'
    SIDE_CHOICES = [(SIDE_OFFER, 'Donné'), (SIDE_REQUEST, 'Demandé')]

    trade = models.ForeignKey(Trade, on_delete=models.CASCADE, related_name='lines')
    side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='+')
    quantity = models.PositiveIntegerField(default=1)


class Duel(models.Model):
    """Duel amical : les deux héros ont accepté, aucune blessure ni perte."""

    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_FINISHED = 'finished'
    STATUS_DECLINED = 'declined'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Défi lancé'),
        (STATUS_ACTIVE, 'En cours'),
        (STATUS_FINISHED, 'Terminé'),
        (STATUS_DECLINED, 'Refusé'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    challenger = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='duels_sent')
    opponent = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='duels_received')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    challenger_hp = models.PositiveIntegerField(default=0)
    opponent_hp = models.PositiveIntegerField(default=0)
    challenger_max_hp = models.PositiveIntegerField(default=0)
    opponent_max_hp = models.PositiveIntegerField(default=0)
    # Actions secrètes de la manche en cours ('' = pas encore choisie). Voir engine/duel.py.
    challenger_action = models.CharField(max_length=12, blank=True, default='')
    opponent_action = models.CharField(max_length=12, blank=True, default='')
    # Ébranlé (Intimidation subie) : ne peut que Frapper ou se garder à la manche en cours.
    challenger_shaken = models.BooleanField(default=False)
    opponent_shaken = models.BooleanField(default=False)
    # Observer réussi : voit l'action adverse de la manche en cours dès qu'elle est choisie.
    challenger_insight = models.BooleanField(default=False)
    opponent_insight = models.BooleanField(default=False)
    winner = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    round = models.PositiveIntegerField(default=0)
    log = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Duel"

    def __str__(self):
        return f"{self.challenger.name} contre {self.opponent.name} ({self.get_status_display()})"

    def other(self, character):
        return self.opponent if character.pk == self.challenger_id else self.challenger


class WorldEvent(Illustrated):
    """Événement de serveur : une menace commune dont tous les héros entament les points de vie."""

    VISUAL_FOLDER = 'evenements'

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField("Nom", max_length=100)
    description = models.TextField("Récit (BBCode)", blank=True)
    location = models.ForeignKey(Location, verbose_name="Lieu", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='+', help_text="Vide = attaquable de partout.")
    monster = models.ForeignKey(Monster, verbose_name="Créature (illustration de secours)", on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    hp_total = models.PositiveIntegerField("PV de la menace", default=500)
    hp_left = models.PositiveIntegerField("PV restants", default=500)
    hit_difficulty = models.PositiveSmallIntegerField("Seuil pour la toucher", choices=DIFFICULTY_CHOICES,
                                                      default=DIFFICULTY_MEDIUM)
    dodge_difficulty = models.PositiveSmallIntegerField("Seuil pour esquiver sa riposte", choices=DIFFICULTY_CHOICES,
                                                        default=DIFFICULTY_MEDIUM)
    damage_min = models.PositiveSmallIntegerField("Dégâts de riposte min", default=2)
    damage_max = models.PositiveSmallIntegerField("Dégâts de riposte max", default=6)
    cooldown_minutes = models.PositiveSmallIntegerField("Délai entre deux assauts d'un héros (minutes)", default=30)
    starts_at = models.DateTimeField("Début")
    ends_at = models.DateTimeField("Fin")
    reward_xp = models.PositiveIntegerField("XP pour chaque participant", default=50)
    reward_coins = models.PositiveIntegerField("Écus pour chaque participant", default=20)
    top_reward_item = models.ForeignKey(Item, verbose_name="Objet pour le meilleur participant",
                                        on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    rewards_given = models.BooleanField(default=False)
    log = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-starts_at']
        verbose_name = "Événement de serveur"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.hp_left = self.hp_total  # une menace neuve démarre à pleine vie
        super().save(*args, **kwargs)

    @property
    def is_defeated(self):
        return self.hp_left == 0

    @property
    def hp_display(self):
        return f"{self.hp_left} / {self.hp_total}"

    @property
    def status_label(self):
        from django.utils import timezone

        now = timezone.now()
        if self.hp_left == 0:
            return "Vaincu"
        if now < self.starts_at:
            return "À venir"
        if now >= self.ends_at:
            return "Échec"
        return "En cours"

    @property
    def visual_url(self):
        own = super().visual_url
        if own or not self.monster_id:
            return own
        return self.monster.visual_url


class EventParticipation(models.Model):
    event = models.ForeignKey(WorldEvent, on_delete=models.CASCADE, related_name='participations')
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='event_participations')
    damage = models.PositiveIntegerField(default=0)
    attacks = models.PositiveIntegerField(default=0)
    last_attack_at = models.DateTimeField(null=True, blank=True)
    rewarded = models.BooleanField(default=False)

    class Meta:
        ordering = ['-damage']
        constraints = [
            models.UniqueConstraint(fields=['event', 'character'], name='unique_event_participation'),
        ]
