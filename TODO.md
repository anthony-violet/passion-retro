# TODO — Préparation déploiement production

## 🔴 Bloquants (à corriger avant mise en prod)

- [x] Passer `DEBUG=False` dans `.env` ✓
- [ ] Ajouter `SECURE_SSL_REDIRECT=True` dans `settings.py`
- [ ] Ajouter `SESSION_COOKIE_SECURE=True` dans `settings.py`
- [ ] Ajouter `CSRF_COOKIE_SECURE=True` dans `settings.py`
- [ ] Ajouter `SECURE_HSTS_SECONDS=31536000` dans `settings.py`
- [x] Configurer gunicorn avec workers dans `docker-compose.yml` : `--workers 4 --timeout 60` ✓
- [ ] Fixer `requirements.txt` avec les versions exactes (faire `pip freeze > requirements.txt`)

## 🟡 À corriger rapidement

- [x] Changer `MARIADB_ROOT_PASSWORD` dans `docker-compose.yml` ✓
- [x] Remplacer `SITE_URL` par le vrai domaine dans `.env` → `https://nostalgeek.ivakar.com` ✓
- [x] Ajouter un reverse proxy nginx devant gunicorn ✓ (`/home/toine/nginx/conf.d/nostalgeek.conf`)
- [x] Retirer les IP et URLs locales de `CSRF_TRUSTED_ORIGINS` pour la prod ✓
- [ ] Configurer le logging dans `settings.py` (erreurs silencieuses avec `DEBUG=False`)

## 🚀 Déploiement nostalgeek.ivakar.com — étapes restantes

Les fichiers sont prêts. Il reste 3 commandes à exécuter **dans l'ordre** :

### 1. Obtenir le certificat SSL (à lancer dans un vrai terminal en root)
```bash
sudo certbot certonly --webroot -w /home/toine/nginx/html -d nostalgeek.ivakar.com --non-interactive --agree-tos -m violet.anthony90@gmail.com
```

### 2. Démarrer les containers passion-retro
```bash
cd /home/toine/mes_apps/passion-retro && docker compose up -d --build
```

### 3. Activer le HTTPS dans nginx
Dans `/home/toine/nginx/conf.d/nostalgeek.conf`, décommenter le bloc `server { listen 443 ssl; ... }` puis :
```bash
docker exec nginx_global nginx -s reload
```

## 🟢 Ce qui est déjà bon / fait

- Architecture Docker correcte (services db + web, volumes nommés)
- Email SMTP Gmail fonctionnel et testé
- Handlers d'erreur 400 / 403 / 404 / 500 en place
- MariaDB configuré avec `utf8mb4` + `STRICT_TRANS_TABLES`
- `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` configurés
- `SECRET_KEY`, credentials DB et API keys dans `.env` (non versionné)
- Confirmation email allauth fonctionnelle (HMAC)
- Signal `email_confirmed` → `user.active = True` en place
- 71 tests unitaires qui passent
- WhiteNoise ajouté pour servir les statics avec `DEBUG=False`
- `passion_retro_web` sur le `global_network` Docker (visible par nginx)
- Config nginx `nostalgeek.conf` créée (HTTP actif, HTTPS prêt en commentaire)
