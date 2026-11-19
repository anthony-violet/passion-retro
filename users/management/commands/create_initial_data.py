from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée les données initiales nécessaires au fonctionnement du site"

    def handle(self, *args, **options):
        self._create_shop_categories()
        self._create_shop_items()
        self._create_retrobot()
        self._create_forum_categories()
        self._create_posts_categories()
        self._create_nav_sections()
        self._create_game_categories()
        self._create_maintenance()
        self.stdout.write(self.style.SUCCESS("Données initiales créées avec succès."))

    def _create_shop_categories(self):
        from shop.models import Category
        categories = [
            {"name": "cadres", "description": "Cadres pour avatar"},
            {"name": "themes", "description": "Thèmes pour le site"},
            {"name": "Décoration pseudo", "description": "Décorations pour le pseudo"},
            {"name": "Consommables", "description": "Potions et bonus à usage unique"},
        ]
        for data in categories:
            obj, created = Category.objects.get_or_create(name=data["name"], defaults={"description": data["description"], "image": ""})
            if created:
                self.stdout.write(f"  [shop] Catégorie créée : {obj.name}")

    def _create_shop_items(self):
        from shop.models import Category, Item
        items = [
            {"category": "cadres", "name": "Cadre défaut", "description": "Cadre de base", "price": 0, "kind": "frame"},
            {"category": "themes", "name": "Thème RPG", "description": "Débloque le thème RPG", "price": 150, "kind": "theme", "css_class": "rpg", "rarity": "rare"},
            {"category": "themes", "name": "Thème Modern", "description": "Débloque le thème Modern", "price": 200, "kind": "theme", "css_class": "modern", "rarity": "rare"},
            {"category": "themes", "name": "Thème Rétro 80s", "description": "Débloque le thème 80s", "price": 250, "kind": "theme", "css_class": "80s", "rarity": "epic"},
            {"category": "Décoration pseudo", "name": "Décoration défaut", "description": "Décoration de base pour le pseudo", "price": 0, "kind": "username"},
            {"category": "Consommables", "name": "Potion d'XP", "description": "Double l'XP gagnée pendant 24 heures.", "price": 80, "kind": "consumable", "effect": "xp_boost", "rarity": "rare"},
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
                        "kind": data.get("kind", "collectible"),
                        "css_class": data.get("css_class", ""),
                        "effect": data.get("effect", ""),
                        "rarity": data.get("rarity", "common"),
                        "image": "",
                    }
                )
                if created:
                    self.stdout.write(f"  [shop] Item créé : {obj.name}")
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  [shop] Catégorie introuvable : {data['category']}"))

    def _create_retrobot(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        bot, created = User.objects.get_or_create(
            username="RetroBot",
            defaults={"email": "retrobot@example.com", "is_active": True},
        )
        if created:
            bot.set_unusable_password()
            bot.save(update_fields=["password"])
            self.stdout.write("  [users] Utilisateur créé : RetroBot")

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

    def _create_nav_sections(self):
        from posts.models import NavSection, Category
        sections = [
            {"label": "Jeux", "category": "Jeux", "order": 1},
            {"label": "Films & Series", "category": "Films & Series", "order": 2},
            {"label": "Musique", "category": "Musique", "order": 3},
            {"label": "Technologies", "category": "Technologies", "order": 4},
        ]
        for data in sections:
            category, _ = Category.objects.get_or_create(name=data["category"])
            obj, created = NavSection.objects.get_or_create(
                label=data["label"],
                defaults={"category": category, "order": data["order"]},
            )
            if created:
                self.stdout.write(f"  [posts] Section navbar créée : {obj.label}")

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
