"""Règles VALIDÉES d'Ivakar (au 15 novembre 2026). Ne rien inventer ici.

Tout ce qui n'est pas encore tranché par les règles (combat, PV, déclencheurs…)
vit ailleurs et est marqué « PROVISOIRE » : voir ``ivakar_rpg/REGLES.md``.
"""
from dataclasses import dataclass

from ..models import DIFFICULTY_EASY, DIFFICULTY_HARD, DIFFICULTY_MEDIUM, Wound
from .dice import get_rng

# --- III. Résolution des actions ------------------------------------------
DIFFICULTY_LABELS = {DIFFICULTY_EASY: "Facile", DIFFICULTY_MEDIUM: "Moyenne", DIFFICULTY_HARD: "Difficile"}

# --- IV. Personnages -------------------------------------------------------
# code -> (nom, fonction de référence, ordre)
CHARACTERISTICS = {
    'force': ("Force", "Puissance physique brute et effort musculaire.", 1),
    'constitution': ("Constitution", "Vitalité, résistance corporelle, endurance physique et récupération.", 2),
    'dexterite': ("Dextérité", "Fluidité du mouvement, équilibre, précision et coordination.", 3),
    'perception': ("Perception", "Détection et première interprétation des informations de l'environnement.", 4),
    'intelligence': ("Intelligence", "Compréhension, raisonnement, apprentissage, planification et traitement "
                                     "logique de l'information.", 5),
    'mental': ("Mental", "Résistance psychologique, détermination et discipline face à la pression.", 6),
    'charisme': ("Charisme", "Effet produit sur autrui : convaincre, impressionner, intimider, inspirer "
                             "ou captiver.", 7),
}
START_MIN = 1
START_MAX = 20
STAT_CAP = 100
MAX_LEVEL = 25
POINTS_PER_LEVEL = 3

# --- V. Blessures ----------------------------------------------------------
AGGRAVATION_COEFFICIENTS = {
    Wound.SEVERITY_LIGHT: 5,
    Wound.SEVERITY_MODERATE: 4,
    Wound.SEVERITY_SEVERE: 3,
}


@dataclass
class Resolution:
    dice: tuple
    value: int
    bonus: int
    total: int
    threshold: int
    success: bool

    def describe(self, name):
        label = DIFFICULTY_LABELS.get(self.threshold, "")
        verdict = "réussite" if self.success else "échec"
        return (f"{name} : 2D6 ({self.dice[0]}+{self.dice[1]}) + ⌊{self.value} ÷ 3⌋ ({self.bonus}) = {self.total}, "
                f"seuil {self.threshold}{f' ({label})' if label else ''} → {verdict}.")


def bonus(value):
    """⌊caractéristique ÷ 3⌋."""
    return max(0, int(value)) // 3


def resolve(value, threshold, rng=None):
    """Résultat = 2D6 + ⌊caractéristique ÷ 3⌋ ; réussite si le total atteint le seuil."""
    rng = get_rng(rng)
    dice = (rng.randint(1, 6), rng.randint(1, 6))
    b = bonus(value)
    total = dice[0] + dice[1] + b
    return Resolution(dice=dice, value=int(value), bonus=b, total=total, threshold=threshold,
                      success=total >= threshold)


@dataclass
class AggravationCheck:
    roll: int
    threshold: int
    stable: bool


def aggravation_check(stat_value, severity, rng=None):
    """D10 × 10 comparé au seuil de stabilisation (caractéristique × coefficient de gravité).

    Contexte : caractéristique = Force. Temps sans soins : caractéristique = Mental.
    Les deux risques sont indépendants et ne se compensent pas.
    """
    rng = get_rng(rng)
    threshold = int(stat_value) * AGGRAVATION_COEFFICIENTS[severity]
    roll = rng.randint(1, 10) * 10
    return AggravationCheck(roll=roll, threshold=threshold, stable=roll <= threshold)
