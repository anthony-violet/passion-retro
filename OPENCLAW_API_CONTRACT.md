# OPENCLAW_API_CONTRACT.md - NostalGeek Forum API Contract

**Generated from code inspection of `/home/toine/mes_apps/passion-retro/forum_api/`**
**Target agent: OpenClaw `nostalgeek-cm`**

---

## 1. Authentification

### Header attendu
```
Authorization: Bearer <CLÉ_API>
```

### Format de la clé
- La clé est comparée directement en texte clair via `hmac.compare_digest()`.
- On attend la valeur brute de la variable d'environnement `OPENCLAW_API_KEY`.
- Le préfixe `Bearer` est retiré automatiquement avant comparaison.
- **Aucun encodage Base64** n'est utilisé (simplification délibérée).

### Identité API attendue

L'utilisateur API est récupéré depuis `settings.OPENCLAW_API_USER`. Deux valeurs sont à distinguer :

**Valeur par défaut du projet** (développement) : `"openclaw"`
- Définie dans `passion_retro/settings.py` : `os.getenv("OPENCLAW_API_USER", "openclaw")`
- Utilisée par défaut si la variable d'environnement n'est pas définie.
- C'est la valeur de fallback utilisée dans les tests (`test_settings.py` : `OPENCLAW_API_USER = "Frce4"` mais le décorateur `api_auth_required` charge cet utilisateur).

**Valeur de production** : `"Frce4"`
- Chargée depuis la variable d'environnement `OPENCLAW_API_USER` en production.
- Doit correspondre à un utilisateur existant dans la base `get_user_model()`.
- C'est l'utilisateur qui reçoit les points d'expérience (+15 pour création de sujet, +10 pour création de post) dans l'environnement de déploiement.

**Comportement** :
- Si `settings.OPENCLAW_API_USER` est vide/`None`, l'API retourne 401 "Compte API non configuré".
- L'utilisateur assigné à `request.api_user` détermine qui reçoit l'expérience et dont le username apparaît dans les réponses.
- L'agent OpenClaw doit configurer `OPENCLAW_API_USER=Frce4` (ou l'utilisateur correspondant) dans son environnement.

### Comportement en cas d'erreur 401

| Scénario | Code de réponse | Message JSON |
|---|---|---|
| Aucun header `Authorization` | 401 | `{"error": "Unauthorized", "message": "Clé API invalide ou manquante"}` |
| Header `Bearer` sans token (ex: `Bearer `) | 401 | `{"error": "Unauthorized", "message": "Clé API invalide ou manquante"}` |
| Clé incorrecte | 401 | `{"error": "Unauthorized", "message": "Clé API invalide ou manquante"}` |
| Clé API non configurée (vide) | 401 | `{"error": "Unauthorized", "message": "Compte API non configuré"}` |

**Toutes les endpoints nécessitent l'en-tête `Authorization: Bearer <clé>` sauf l'endpoint racine `/api/forum/`.**

---

## 2. Endpoints

### Convention d'URL de base
Toutes les URLs ci-dessous s'appuient sur la base `https://nostalgeek.ivakar.com/api/forum/`

#### `GET /api/forum/`
- **Description**: Racine de l'API, renvoie la documentation auto-génée des endpoints.
- **Authentification**: Non protégée (aucune clé requise).
- **Réponse**:
```json
{
  "message": "API Forum OpenClaw",
  "endpoints": {
    "categories": "/api/forum/categories/",
    "forums": "/api/forum/forums/",
    "topics": "/api/forum/topics/"
  }
}
```

---

#### `GET /api/forum/categories/`
- **Description**: Liste toutes les catégories de forums.
- **Méthode**: GET
- **Authentification**: Requise (`Authorization: Bearer <clé>`)
- **Paramètres**: Aucun (filtre staté `state='open'` côté sujet uniquement)
- **Réponse JSON**:
```json
{
  "count": 5,
  "categories": [
    {
      "id": 1,
      "name": "Jeux Vidéo",
      "description": "Les jeux vidéo rétro",
      "created": "2024-01-15T10:30:00Z",
      "updated": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

#### `GET /api/forum/forums/`
- **Description**: Liste tous les forums avec leurs catégories et auteurs.
- **Méthode**: GET
- **Authentification**: Requise (`Authorization: Bearer <clé>`)
- **Paramètres**: Aucun
- **Réponse JSON**:
```json
{
  "count": 3,
  "forums": [
    {
      "id": 1,
      "category__name": "Jeux Vidéo",
      "name": "Jeux de plateau",
      "description": "Discutez de vos jeux de plateau préférés",
      "author__username": "admin",
      "created": "2024-01-15T10:30:00Z",
      "updated": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

#### `GET /api/forum/topics/`
- **Description**: Liste les sujets de discussion avec pagination et filtres.
- **Méthode**: GET
- **Authentification**: Requise (`Authorization: Bearer <clé>`)
- **Paramètres de query string**:
  - `forum_id` (entier, optionnel): Filtrer les sujets par ID de forum.
  - `limit` (entier, par défaut `50`): Nombre de résultats par page.
  - `offset` (entier, par défaut `0`): Décalage pour la pagination.
- **Filtres implicites**: Uniquement les sujets avec `state='open'` sont retournés.
- **Réponse JSON**:
```json
{
  "count": 12,
  "limit": 50,
  "offset": 0,
  "topics": [
    {
      "id": 1,
      "forum_id": 1,
      "forum_name": "Jeux de plateau",
      "title": "Nouveau sujet",
      "author_id": 42,
      "author_username": "testuser",
      "author_level_number": 1,
      "author_level_title": "Novice",
      "created": "2025-03-10T14:20:00Z",
      "updated": "2025-03-10T14:25:00Z",
      "views": 23,
      "posts_count": 3,
      "last_post": {
        "id": 7,
        "created": "2025-03-10T14:55:00Z",
        "author_id": 42,
        "author_username": "testuser"
      }
    }
  ]
}
```

---

#### `GET /api/forum/topics/{topic_id}/`
- **Description**: Consulte un sujet unique avec l'ensemble de ses posts.
- **Méthode**: GET
- **Authentification**: Requise (`Authorization: Bearer <clé>`)
- **Paramètres de chemin**: `topic_id` (entier)
- **Réponse JSON**:
```json
{
  "id": 1,
  "forum_id": 1,
  "forum_name": "Jeux de plateau",
  "title": "Premier sujet",
  "author_id": 42,
  "author_username": "testuser",
  "author_level_number": 1,
  "author_level_title": "Novice",
  "created": "2025-03-10T14:20:00Z",
  "updated": "2025-03-10T14:45:00Z",
  "state": "open",
  "views": 42,
  "posts": [
    {
      "id": 1,
      "author_id": 42,
      "author_username": "testuser",
      "created": "2025-03-10T14:21:00Z",
      "updated": "2025-03-10T14:21:00Z",
      "content": "Bonjour à tous !",
      "active": true
    }
  ]
}
```

---

#### `POST /api/forum/topics/create/`
- **Description**: Crée un nouveau sujet ainsi que son premier message. Accorde 15 expérience à l'utilisateur API.
- **Méthode**: POST
- **Authentification**: Requise (`Authorization: Bearer <clé>`)
- **Corps JSON** (application/json):
  - `forum_id` (entier, requis): ID du forum dans lequel créer le sujet.
  - `title` (chaîne, requis): Titre du sujet (validé non vide).
  - `content` (chaîne, requis): Contenu du premier message (validé non vide).
- **Codes de réponse**:
  - `201 Créé`: Sujet et message créés avec succès.
  - `400 Mauvaise demande`: Titre ou contenu manquant/vide.
  - `401 Non autorisé`: Clé invalide ou manquante.
- **Exemple de demande**:
```bash
curl -X POST -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"forum_id": 1, "title": "Nouveau sujet", "content": "Premier message"}' \
     https://nostalgeek.ivakar.com/api/forum/topics/create/
```
- **Réponse JSON (201)**:
```json
{
  "id": 42,
  "forum_id": 1,
  "forum_name": "Jeux de plateau",
  "title": "Nouveau sujet",
  "author_id": 42,
  "author_username": "Frce4",
  "author_level_number": 10,
  "author_level_title": "Membre",
  "created": "2025-06-15T10:00:00Z",
  "updated": "2025-06-15T10:00:00Z",
  "views": 0,
  "content": "Nouveau sujet"
}
```

---

#### `POST /api/forum/topics/{topic_id}/posts/`
- **Description**: Crée un nouveau message au sein d'un sujet existant. Accorde 10 expérience à l'utilisateur API.
- **Méthode**: POST
- **Authentification**: Requise (`Authorization: Bearer <clé>`)
- **Paramètres de chemin**: `topic_id` (entier, requis)
- **Corps JSON** (application/json):
  - `content` (chaîne, requis): Contenu du message (validé non vide).
- **Codes de réponse**:
  - `201 Créé`: Message créé avec succès.
  - `403 Interdit`: Le sujet est verrouillé (`state='closed'`).
  - `400 Mauvaise demande`: Contenu manquant/vide.
  - `404 Non trouvé`: Topic introuvable.
  - `401 Non autorisé`: Clé invalide ou manquante.
- **Exemple de demande**:
```bash
curl -X POST -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"content": "Réponse via API"}' \
     https://nostalgeek.ivakar.com/api/forum/topics/1/posts/
```
- **Réponse JSON (201)**:
```json
{
  "id": 7,
  "topic_id": 1,
  "author_id": 42,
  "author_username": "Frce4",
  "created": "2025-06-15T10:10:00Z",
  "updated": "2025-06-15T10:10:00Z",
  "content": "Réponse via API",
  "active": true
}
```

---

## 3. Fonctionnalités disponibles

| Fonctionnalité | Endpoint | Méthode | Description |
|---|---|---|---|
| Lire les catégories | `GET /api/forum/categories/` | GET | Liste toutes les catégories disponibles |
| Lire les forums | `GET /api/forum/forums/` | GET | Liste tous les forums avec leurs catégories et auteurs |
| Lister les sujets | `GET /api/forum/topics/` | GET | Liste les sujets ouverts avec pagination et filtrage par forum |
| Consulter un sujet | `GET /api/forum/topics/{topic_id}/` | GET | Retourne le sujet complet avec tous ses posts |
| Lire les messages d'un sujet | `GET /api/forum/topics/{topic_id}/` (via `posts` inclus) | GET | Retourne tous les posts actifs d'un sujet |
| Créer un sujet | `POST /api/forum/topics/create/` | POST | Crée un sujet + premier message ; +15 exp à l'utilisateur |
| Répondre à un sujet | `POST /api/forum/topics/{topic_id}/posts/` | POST | Crée un nouveau message ; +10 exp ; interdit si sujet clos |

**Fonctionnalités manquantes (non implémentées dans le code)**:
- Suppression de sujet ou de message
- Modification de sujet ou de message
- Recherche par titre
- Filtres supplémentaires au-delà de `forum_id` et `state='open'`
- Endpoints de connexion/déconnexion dédiés

---

## 4. Pagination et erreurs

### Paramètres de pagination (uniquement `GET /api/forum/topics/`)

| Paramètre | Type | Valeur par défaut | Description |
|---|---|---|---|
| `limit` | entier | 50 | Nombre maximum de sujets par page |
| `offset` | entier | 0 | Décalage de départ dans la liste |

**Syntaxe**: `/api/forum/topics/?limit=10&offset=0`

**Comportement actuel (code)**:
- La requête construit d'abord `Topic.objects.filter(state='open')`.
- Si `forum_id` est fourni, filtre ajoute `forum_id=forum_id`.
- Puis applique le slicing: `query[:limit][offset:]`.
- **Note**: Ce pattern de slicing Python est problématique pour `offset > 0` :
  - `offset=0` retourne correctement les `limit` premiers éléments
  - `offset > 0` ne saute pas correctement les éléments (bug de pagination)
- La réponse inclut `count`, `limit`, `offset`, et la liste `topics`.

**Comportement attendu (formule correcte)**:
- La formule idéale serait `query[offset:offset+limit]` qui fournirait une pagination correcte :
  - `offset=0, limit=10` → éléments 0 à 9
  - `offset=10, limit=10` → éléments 10 à 19
  - `offset=20, limit=10` → éléments 20 à 29

**Limite**: Aucune limite stricte côté serveur autre que la mémoire; `limit` et `offset` sont simples entiers Python.

### Codes HTTP et formats d'erreur

| Code | Situation | Format de réponse |
|---|---|---|
| `200` | Succès pour GET/listes/create sans conflit | `{... données ...}` |
| `201` | Création réussie (topic ou post) | `{... données ...}` |
| `400` | Données invalides (titre/vide manquant) | `{"error": "Bad Request", "message": "Le titre est obligatoire"}` |
| `401` | Clé API manquante ou invalide | `{"error": "Unauthorized", "message": "Clé API invalide ou manquante"}` |
| `403` | Sujet fermé, tentative de post | `{"error": "Forbidden", "message": "Ce sujet est verrouillé"}` |
| `404` | Topic/post introuvable | `{"error": "Not Found", "message": "..."}` (via `get_object_or_404`) |
| `405` | Méthode HTTP non autorisée sur endpoint | `{"error": "Method not allowed"}` |

**Note importante**: L'API n'utilise pas de DRF (Django REST Framework). Tous les codes et formats sont gérés manuellement dans `views.py`.

---

## 5. Exemples d'utilisation

> Remplacez `$OPENCLAW_API_KEY` par votre clé secrète. **N'insérez jamais la clé en clair** dans des dépôts publics.

### Lire les catégories
```bash
curl -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     https://nostalgeek.ivakar.com/api/forum/categories/
```

### Lister les sujets avec pagination
```bash
curl -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     "https://nostalgeek.ivakar.com/api/forum/topics/?limit=5&offset=0"
```

### Consulter un sujet avec ses posts
```bash
curl -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     https://nostalgeek.ivakar.com/api/forum/topics/1/
```

### Créer un sujet
```bash
curl -X POST -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"forum_id": 1, "title": "Nouveau sujet", "content": "Premier message"}' \
     https://nostalgeek.ivakar.com/api/forum/topics/create/
```

### Répondre à un sujet
```bash
curl -X POST -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"content": "Intéressant !"}' \
     https://nostalgeek.ivakar.com/api/forum/topics/1/posts/
```

### Gérer les erreurs
```bash
# Sans clé → 401
curl https://nostalgeek.ivakar.com/api/forum/categories/
# {"error":"Unauthorized","message":"Clé API invalide ou manquante"}

# Clé fausse → 401
curl -H "Authorization: Bearer wrong_key" https://nostalgeek.ivakar.com/api/forum/categories/
# {"error":"Unauthorized","message":"Clé API invalide ou manquante"}

# Post sur sujet clos → 403
curl -X POST -H "Authorization: Bearer $OPENCLAW_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"content": "test"}' \
     https://nostalgeek.ivakar.com/api/forum/topics/1/posts/
# {"error":"Forbidden","message":"Ce sujet est verrouillé"}
```

---

## Résumé des capacités pour OpenClaw

L'API Forum NostalGeek expose **7 endpoints** permettant à l'agent `nostalgeek-cm` d'interagir pleinement avec la communauté :

1. **Lecture** complète : catégories, forums, sujets (avec pagination), sujets complets avec posts.
2. **Écriture** : création de sujets (avec premier message) et réponse/post dans des sujets existants.
3. **Sécurité** : authentification Bearer clé API, protection contre les posts sur sujets fermés, validation des champs requis.
4. **Statistiques** : expérience accordée (+15 pour un nouveau sujet, +10 pour un nouveau message).
5. **Pagination** manuelle via `limit`/`offset` sur la liste des sujets.

**Limites connues** : pas de DRF, pas d'authentification OAuth/token rotation, pas de suppression/ modification, pas de recherche avancée. Toutes les opérations d'écriture nécessitent une clé API valide et l'utilisateur cible doit exister dans la base Django.

L'API est prête à être consommée par OpenClaw avec :
- La variable d'environnement `OPENCLAW_API_KEY` contenant la clé secrète.
- La variable d'environnement `OPENCLAW_API_USER` réglée sur `Frce4` (valeur production) ou `openclaw` (valeur par défaut/development).
- L'utilisateur `Frce4` (ou l'utilisateur configuré) doit exister dans la base Django `auth_user`.

L'API Forum NostalGeek expose **7 endpoints** permettant à l'agent `nostalgeek-cm` d'interagir pleinement avec la communauté :