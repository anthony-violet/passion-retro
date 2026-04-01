from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée les données initiales nécessaires au fonctionnement du site"

    def handle(self, *args, **options):
        self._create_shop_categories()
        self._create_shop_items()
        self._create_forum_categories()
        self._create_posts_categories()
        self._create_game_categories()
        self._create_maintenance()
        self.stdout.write(self.style.SUCCESS("Données initiales créées avec succès."))

    def _create_shop_categories(self):
        from shop.models import Category
        categories = [
            {"name": "cadres", "description": "Cadres pour avatar"},
            {"name": "themes", "description": "Thèmes pour le site"},
            {"name": "Décoration pseudo", "description": "Décorations pour le pseudo"},
        ]
        for data in categories:
            obj, created = Category.objects.get_or_create(name=data["name"], defaults={"description": data["description"], "image": ""})
            if created:
                self.stdout.write(f"  [shop] Catégorie créée : {obj.name}")

    def _create_shop_items(self):
        from shop.models import Category, Item
        items = [
            {"category": "cadres", "name": "Cadre défaut", "description": "Cadre de base", "price": "0.00"},
            {"category": "themes", "name": "Thème 00s", "description": "Thème années 2000", "price": "100.00"},
            {"category": "themes", "name": "Thème RPG", "description": "Thème RPG", "price": "150.00"},
            {"category": "Décoration pseudo", "name": "Décoration défaut", "description": "Décoration de base pour le pseudo", "price": "0.00"},
        ]
        for data in items:
            try:
                category = Category.objects.get(name=data["category"])
                obj, created = Item.objects.get_or_create(
                    name=data["name"],
                    defaults={
                        "category": category,
                        "description": data["description"],
                        "price": data["price"],
                        "image": "",
                    }
                )
                if created:
                    self.stdout.write(f"  [shop] Item créé : {obj.name}")
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  [shop] Catégorie introuvable : {data['category']}"))

    def _create_forum_categories(self):
        from forum.models import Category
        categories = [
            {"name": "Général", "description": "Discussions générales"},
            {"name": "Jeux vidéo rétro", "description": "Parlons des jeux d'époque"},
            {"name": "Cinéma & Séries", "description": "Films et séries cultes"},
            {"name": "Musique", "description": "La musique d'hier et d'aujourd'hui"},
            {"name": "Aide & Support", "description": "Besoin d'aide sur le site ?"},
        ]
        for data in categories:
            obj, created = Category.objects.get_or_create(name=data["name"], defaults={"description": data["description"]})
            if created:
                self.stdout.write(f"  [forum] Catégorie créée : {obj.name}")

    def _create_posts_categories(self):
        from posts.models import Category
        categories = ["Actualités", "Dossiers", "Tests", "Rétro"]
        for name in categories:
            obj, created = Category.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f"  [posts] Catégorie créée : {obj.name}")

    def _create_game_categories(self):
        from games.models import LittleBacCategories
        categories = [
            {"name": "Prénom", "description": "Un prénom"},
            {"name": "Nom de famille", "description": "Un nom de famille"},
            {"name": "Pays", "description": "Un pays du monde"},
            {"name": "Ville", "description": "Une ville"},
            {"name": "Animal", "description": "Un animal"},
            {"name": "Plante / Fleur", "description": "Une plante ou une fleur"},
            {"name": "Objet", "description": "Un objet du quotidien"},
            {"name": "Métier", "description": "Un métier"},
            {"name": "Célébrité", "description": "Une célébrité"},
            {"name": "Jeu vidéo", "description": "Un jeu vidéo"},
            {"name": "Film", "description": "Un film"},
            {"name": "Série TV", "description": "Une série télévisée"},
            {"name": "Marque", "description": "Une marque commerciale"},
            {"name": "Sport", "description": "Un sport"},
            {"name": "Couleur", "description": "Une couleur"},
        ]
        for data in categories:
            obj, created = LittleBacCategories.objects.get_or_create(name=data["name"], defaults={"description": data["description"]})
            if created:
                self.stdout.write(f"  [games] Catégorie Petit Bac créée : {obj.name}")

    def _create_maintenance(self):
        from maintenance.models import Informations
        obj, created = Informations.objects.get_or_create(
            defaults={
                "name": "Maintenance en cours",
                "content": "Le site est temporairement indisponible pour maintenance. Revenez bientôt !",
                "is_active": False,
            }
        )
        if created:
            self.stdout.write("  [maintenance] Message de maintenance créé.")
