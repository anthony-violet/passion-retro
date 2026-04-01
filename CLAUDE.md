# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commandes de développement

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Lancer le serveur de développement (port 5500)
python manage.py runserver 0.0.0.0:5500

# Migrations
python manage.py makemigrations
python manage.py migrate

# Fichiers statiques
python manage.py collectstatic --noinput

# Lancer les tests (utilise SQLite en mémoire)
python manage.py test --settings=passion_retro.test_settings

# Lancer les tests d'une seule app
python manage.py test forum --settings=passion_retro.test_settings
```

## Docker

```bash
docker-compose up --build   # démarre MariaDB + app Django sur http://localhost:5500
```

Le `docker-compose.yml` lance automatiquement `migrate` et `collectstatic` au démarrage.

## Configuration de l'environnement

Toutes les variables de config sont dans `.env` (non versionné) :
- `DATABASE_ENGINE` : si vide → SQLite, si `django.db.backends.mysql` → MariaDB
- `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- `GOOGLE_PUBLIC_KEY`, `GOOGLE_PRIVATE_KEY` (reCAPTCHA)

**Sans Docker**, pour utiliser MariaDB il faut que `DATABASE_ENGINE=django.db.backends.mysql` soit défini dans `.env` et que MariaDB soit accessible sur l'hôte configuré.

## Architecture

Projet Django 4.2 — plateforme communautaire rétro. 11 apps Django :

| App | Rôle |
|-----|------|
| `users` | Modèle utilisateur custom (AbstractUser), avatars, niveaux, expérience, inventaire |
| `forum` | Forums avec catégories, topics, posts |
| `posts` | Articles/news avec workflow de validation |
| `gallery` | Galerie d'images |
| `quiz` | Système de quiz avec workflow de validation |
| `messagerie` | Messages privés |
| `shop` | Boutique avec items et inventaire utilisateur |
| `tchat` | Chat |
| `guestbook` | Livre d'or |
| `games` | Jeux |
| `maintenance` | Mode maintenance du site |

### Points clés

- **Modèle utilisateur custom** : `users.models.User` — référencé via `AUTH_USER_MODEL`. Contient avatar, biographie, thème, niveaux, expérience, inventaire shop.
- **Middleware custom** : `UserStatsMiddleware`, `UserLevelMiddleware`, `UserLevelUpMiddleware`, `ForumStatsMiddleware`, `GuestbookMiddleware`, `PostsMiddleware`, `MaintenanceMiddleware`
- **Context processors** : compteurs en temps réel pour posts en attente, quiz en attente, messages privés non lus
- **Parser BBCode** : `commons/bbcode_parser.py` — convertit BBCode en HTML (utilisé dans forum, posts, guestbook)
- **Base de données** : MariaDB en production (Docker), SQLite en développement local. Le basculement se fait via `DATABASE_ENGINE` dans `.env`
- **Tests** : `passion_retro/test_settings.py` utilise SQLite `:memory:` pour les tests
- **Langue** : fr-FR, timezone Europe/Paris
- **Thèmes** : support multi-thèmes (ex: "00s") géré au niveau utilisateur
