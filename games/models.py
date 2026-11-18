from django.db import models
from users.models import User

class LittleBacGames(models.Model):
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games')
    name = models.CharField(max_length=155)
    status = models.CharField(max_length=20 ,choices=[
        ('waiting', 'En attente'),
        ('in_progress', 'En cours'),
        ('finished', 'Terminée')
    ], default='waiting')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    countdown_started = models.BooleanField(default=False)
    countdown_time = models.IntegerField(default=0)
    countdown_start_time = models.DateTimeField(default=None, null=True, blank=True)
    current_phase = models.CharField(max_length=60, default="ready_game", null=True, blank=True)

class LittleBacPlayers(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='players')
    game = models.ForeignKey(LittleBacGames, on_delete=models.CASCADE, related_name='players')
    score = models.IntegerField()
    is_ready = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[
        ('playing', 'Joue'),
        ('overed', 'A fini')
    ], default="playing")

class LittleBacCategories(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(default="")

class LittleBacRounds(models.Model):
    id = models.AutoField(primary_key=True)
    game = models.ForeignKey(LittleBacGames, on_delete=models.CASCADE, related_name='rounds')
    letter = models.CharField(max_length=1)
    round_counter = models.IntegerField(default=1)
    xp_awarded = models.BooleanField(default=False)

class LittleBacAnswers(models.Model):
    id = models.AutoField(primary_key=True)
    round = models.ForeignKey(LittleBacRounds, on_delete=models.CASCADE, related_name='answers')
    player = models.ForeignKey(LittleBacPlayers, on_delete=models.CASCADE, related_name='answers')
    category = models.ForeignKey(LittleBacCategories, on_delete=models.CASCADE, related_name='answers')
    answer = models.CharField(max_length=100)
    is_valid = models.BooleanField(default=False)
    point = models.IntegerField(default=0)

class MysteryGame(models.Model):
    """Jeu mystère du jour : un jeu rétro à deviner grâce à des indices progressifs.

    Un membre peut en proposer un : il reste « en attente » jusqu'à ce que
    l'équipe le valide, puis le programme à une date.
    """

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_APPROVED, 'Validé'),
        (STATUS_REJECTED, 'Refusé'),
    ]

    title = models.CharField("Réponse (nom du jeu)", max_length=155)
    aliases = models.TextField(
        "Réponses acceptées", blank=True, default="",
        help_text="Une variante par ligne (abréviations, titre japonais, sans sous-titre…).",
    )
    publish_date = models.DateField("Jour de publication", unique=True, null=True, blank=True)
    anecdote = models.TextField("Anecdote affichée à la fin", blank=True, default="")
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='mystery_games'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_APPROVED)
    rejection_reason = models.TextField(blank=True, default="")
    reward_granted = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-publish_date', '-id']

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    def __str__(self):
        return self.title

    def accepted_answers(self):
        return [self.title] + [line.strip() for line in self.aliases.splitlines() if line.strip()]


class MysteryClue(models.Model):
    game = models.ForeignKey(MysteryGame, on_delete=models.CASCADE, related_name='clues')
    order = models.PositiveSmallIntegerField(default=1)
    text = models.CharField(max_length=255, blank=True, default="")
    image = models.ImageField(upload_to='mystery_games/', null=True, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Indice {self.order} — {self.game}"


class MysteryAttempt(models.Model):
    STATUS_PLAYING = 'playing'
    STATUS_WON = 'won'
    STATUS_LOST = 'lost'
    STATUS_CHOICES = [
        (STATUS_PLAYING, 'En cours'),
        (STATUS_WON, 'Trouvé'),
        (STATUS_LOST, 'Perdu'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mystery_attempts')
    game = models.ForeignKey(MysteryGame, on_delete=models.CASCADE, related_name='attempts')
    clues_revealed = models.PositiveSmallIntegerField(default=1)
    guesses = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PLAYING)
    xp_earned = models.PositiveIntegerField(default=0)
    gold_earned = models.PositiveIntegerField(default=0)
    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'game'], name='unique_mystery_attempt'),
        ]

    @property
    def is_over(self):
        return self.status != self.STATUS_PLAYING
