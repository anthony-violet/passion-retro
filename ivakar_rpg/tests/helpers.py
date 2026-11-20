from django.core.management import call_command
from django.test import TestCase

from users.models import User

from ..engine import character as hero
from ..models import Character, CharacterCharacteristic, Origin


class FixedRng:
    """Faux hasard : renvoie les valeurs données, dans l'ordre, à chaque ``randint``."""

    def __init__(self, *values):
        self.values = list(values)

    def randint(self, a, b):
        if not self.values:
            raise AssertionError("FixedRng : plus de valeurs prévues")
        value = self.values.pop(0)
        assert a <= value <= b, f"{value} hors de [{a}, {b}]"
        return value


class IvakarTestCase(TestCase):
    """Monde d'exemple chargé + un membre avec un héros (origine Soldat de garnison)."""

    @classmethod
    def setUpTestData(cls):
        call_command('load_ivakar', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username='heros', password='pass', gold=200, is_staff=True)
        self.origin = Origin.objects.get(slug='soldat-garnison')
        self.character = hero.create_character(self.user, "Aldric", self.origin.pk)

    def reload(self):
        self.character = Character.objects.select_related('location', 'scene').get(pk=self.character.pk)
        return self.character

    def set_stat(self, code, value):
        CharacterCharacteristic.objects.filter(character=self.character, characteristic__code=code) \
            .update(value=value)
