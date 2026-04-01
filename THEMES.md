# Guide de création de thèmes Passion Rétro

## Architecture du système de thèmes

Le système utilise un héritage de thème via CSS:
1. `default/theme.css` - contient toutes les variables et styles de base
2. `{theme}/theme.css` - surcharge uniquement les variables souhaitées

## Configuration d'un thème

Les thèmes sont configurés dans `passion_retro/theme_config.py`:

```python
THEME_CONFIGS = {
    'nom_du_theme': {
        'name': 'Nom affiché',
        'extends': 'default',  # thème parent
        'layout': {
            'navbar': 'top',      # top, left, right, none
            'left_menu': True,    # True/False
            'right_menu': True,   # True/False
            'menu_type': 'vertical',  # vertical/horizontal
        },
    },
}
```

## Créer un nouveau thème

### 1. Ajouter la configuration

Dans `passion_retro/theme_config.py`, ajouter une entrée:

```python
'montheme': {
    'name': 'Mon Super Theme',
    'extends': 'default',
    'layout': {
        'navbar': 'top',
        'left_menu': True,
        'right_menu': True,
        'menu_type': 'vertical',
    },
},
```

### 2. Créer le fichier CSS

Créer `static/themes/montheme/theme.css`:

```css
/* Mon Super Theme - Hérité de default */

:root {
    /* Surcharger uniquement les variables désirées */
    
    /* Couleurs de fond */
    --bg-body: #votre_couleur;
    --bg-container: #votre_couleur;
    --bg-menu: #votre_couleur;
    
    /* Couleurs de texte */
    --text-primary: #votre_couleur;
    --text-link: #votre_couleur;
    
    /* Bordures */
    --border-container: #votre_couleu;
    
    /* Boutons */
    --bg-button: linear-gradient(...);
    --text-button: #couleur;
    
    /* Ombres */
    --shadow-container: 0 0 10px rgba(...);
}

/* Styles spécifiques au thème */
body {
    /* Votre background */
}

.container {
    /* Vos styles de conteneur */
}
```

### 3. Variables CSS disponibles

**Couleurs de fond:**
- `--bg-body`, `--bg-container`, `--bg-menu`
- `--bg-post-card`, `--bg-forum-row`, `--bg-forum-row-even`
- `--bg-button`, `--bg-button-hover`, `--bg-button-add`
- `--bg-input`, `--bg-footer`

**Couleurs de texte:**
- `--text-primary`, `--text-link`, `--text-link-hover`
- `--text-button`, `--text-admin`, `--text-sadmin`

**Couleurs de bordure:**
- `--border-container`, `--border-menu-header`
- `--border-button`, `--border-input`

**Dégradés:**
- `--gradient-menu-header`, `--gradient-forum-category`

**Ombres:**
- `--shadow-container`, `--shadow-button`, `--shadow-input-focus`

### 4. Créer le répertoire du thème

```
static/themes/montheme/
├── theme.css          # Obligatoire
├── img/               # Images optionnelles
│   └── bg.png
└── fonts/             # Polices optionnelles
```

## Exemple: thème minimal

```css
/* Theme Minimal - Hérité de default */
:root {
    /*Coachours simples*/
    --bg-body: #f0f0f0;
    --bg-container: #ffffff;
    --text-primary: #333333;
    --text-link: #0066cc;
    --border-container: #cccccc;
    
    /*Boutons*/
    --bg-button: #0066cc;
    --text-button: #ffffff;
    --border-button: #0055aa;
}
```

## Layouts possibles

| Configuration | Layout |
|---------------|--------|
| `left_menu: True, menu_type: vertical` | Menu gauche vertical |
| `left_menu: False, menu_type: horizontal` | Menu horizontal en haut |
| `navbar: none` | Pas de header |
| `right_menu: False` | Sans menu droit |

## Notes

- Le thème `default` doit TOUJOURS être chargé en premier (le layout fait ça automatiquement)
- Les variables non définies héritent de default
- Les styles de default s'appliquent totalement par défaut