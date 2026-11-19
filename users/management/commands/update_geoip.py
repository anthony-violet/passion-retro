"""Télécharge la base gratuite DB-IP « IP to Country Lite » (format .mmdb).

Utilisée par les statistiques internes pour déduire le pays d'un visiteur à
partir de son adresse IP, sans service extérieur et sans conserver l'IP.
DB-IP publie une nouvelle version chaque mois : relancer la commande une fois
par mois suffit. Licence CC BY 4.0 (attribution affichée sur la page des
statistiques du panel).

    python manage.py update_geoip
"""

import gzip
import os
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

URL = 'https://download.db-ip.com/free/dbip-country-lite-{year}-{month:02d}.mmdb.gz'
MAX_SIZE = 50 * 1024 * 1024  # garde-fou : la base pèse environ 4 Mo compressée


def _months_to_try(today):
    """Mois en cours, puis le précédent (la base du mois sort parfois en retard)."""
    previous = date(today.year - 1, 12, 1) if today.month == 1 else date(today.year, today.month - 1, 1)
    return [today, previous]


class Command(BaseCommand):
    help = "Télécharge ou met à jour la base IP → pays (DB-IP Country Lite)."

    def handle(self, *args, **options):
        target = Path(settings.GEOIP_COUNTRY_DB or settings.GEOIP_DEFAULT_PATH)
        target.parent.mkdir(parents=True, exist_ok=True)

        compressed = None
        for month in _months_to_try(date.today()):
            url = URL.format(year=month.year, month=month.month)
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'geoip-update/1.0'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    compressed = response.read(MAX_SIZE + 1)
                break
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise CommandError(f"Téléchargement impossible ({error.code}) : {url}")
                self.stdout.write(f"Pas encore de base pour {month:%m/%Y}, essai du mois précédent…")
            except urllib.error.URLError as error:
                raise CommandError(f"Téléchargement impossible : {error.reason}")
        if compressed is None:
            raise CommandError("Aucune base DB-IP disponible pour ce mois ni le précédent.")
        if len(compressed) > MAX_SIZE:
            raise CommandError("Fichier anormalement gros, téléchargement abandonné.")

        try:
            data = gzip.decompress(compressed)
        except OSError:
            raise CommandError("Le fichier téléchargé n'est pas une archive valide.")

        # Écriture dans un fichier temporaire, vérification, puis remplacement atomique.
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix='.mmdb.tmp')
        try:
            with os.fdopen(fd, 'wb') as tmp:
                tmp.write(data)
            self._check(tmp_path)
            os.chmod(tmp_path, 0o644)  # lisible par le serveur, quel que soit son utilisateur
            os.replace(tmp_path, target)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        self.stdout.write(self.style.SUCCESS(
            f"Base IP → pays installée : {target} ({len(data) // 1024} Ko). "
            "Redémarre le serveur pour qu'elle soit prise en compte."
        ))

    def _check(self, path):
        try:
            import maxminddb
        except ImportError:
            raise CommandError("Le paquet « maxminddb » est requis : pip install -r requirements.txt")
        try:
            with maxminddb.open_database(path) as reader:
                record = reader.get('8.8.8.8') or {}
        except Exception as error:
            raise CommandError(f"Base invalide : {error}")
        if not (record.get('country') or {}).get('iso_code'):
            raise CommandError("Base invalide : aucun pays trouvé pour une adresse de test.")
