"""Règles d'Ivakar.

Chaque action du joueur est une fonction qui reçoit le personnage, le verrouille
en base (``select_for_update``) dans une transaction, applique les règles et
renvoie le personnage à jour. Une action refusée lève ``RpgError`` dont le
message s'affiche tel quel au joueur.
"""


class RpgError(Exception):
    """Action refusée ; le message s'affiche tel quel au joueur."""
