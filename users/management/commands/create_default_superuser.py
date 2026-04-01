from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée le superutilisateur par défaut (Toine/test) si la base est vide"

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.exists():
            User.objects.create_superuser(username="Toine", password="test")
            self.stdout.write(self.style.SUCCESS("Superutilisateur Toine créé."))
        else:
            self.stdout.write("Des utilisateurs existent déjà, aucune action effectuée.")
