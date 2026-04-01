#!/usr/bin/env python3
"""
Script pour convertir un dump MariaDB en fixture Django compatible SQLite.

Amélioré pour:
- Lire les structures de tables (CREATE TABLE) pour obtenir les noms de colonnes.
- Mapper les tables MariaDB aux modèles Django.
- Gérer correctement les types de données (booléens, NULL, dates).
- Parser robustement les instructions INSERT multi-lignes et les caractères spéciaux.
"""

import re
import json
import sys
from pathlib import Path

# Mapping personnalisable des tables MariaDB vers les modèles Django
TABLE_TO_MODEL = {
    # Formats standards
    'auth_user': 'users.user',
    'auth_group': 'auth.group',
    'auth_permission': 'auth.permission',
    'django_content_type': 'contenttypes.contenttype',
    
    # Votre projet
    'blog_post': 'posts.post',
    'core_maintenance': 'maintenance.informations',
    'users_profile': 'users.user', # Fusionné dans le modèle User
}

# Renommage des champs par table: { 'table_name': { 'sql_field': 'django_field' } }
# Si django_field est None, le champ sera ignoré.
FIELD_MAPPINGS = {
    'blog_post': {
        'name': 'title',
        'enable': 'active',
        'created_at': 'created',
        'updated_at': 'updated',
        'tags': None, 
        'description': None,
        # Ajout de champs par défaut pour les champs obligatoires absents du SQL
        '__defaults__': {
            'category_id': 1,
            'type': 'news',
            'author_id': 1,
            'parent': True,
            'contribution': False,
        }
    },
    'core_maintenance': {
        'message': 'content',
        'start_date': None,
        'end_date': None,
    },
    'auth_user': {
        'is_active': 'is_active', 
    },
    'users_profile': {
        'user_id': 'pk', # Utiliser user_id comme clé primaire pour la fusion
        'id': None, # Ignorer l'ID propre de la table profile
        'is_premium': None,
        'first_name': None, 
        'last_name': None,  
        'username': None,   # TRÈS IMPORTANT: Ne pas inclure username ici
        'birth_date': 'birth_date',
        'biography': 'biography',
        'avatar': 'avatar',
    }
}

# Tables à ignorer lors de la conversion
TABLES_TO_IGNORE = [
    'django_migrations',
    'django_session',
    'django_admin_log',
    'django_content_type',
    'auth_permission',
    'auth_group',
    'auth_group_permissions',
    'auth_user_groups',
    'auth_user_user_permissions',
    # 'users_profile', # On ne l'ignore plus
    'core_sitesettings',
    'core_visit',
    'courses_comment',
    'courses_course',
    'courses_lesson',
    'courses_module',
    'discord_integration_discordlevel',
    'discord_integration_discordnotification',
    'progression_progression',
    'progression_progression_completed_lessons',
]

def parse_sql_values(values_str):
    """
    Parse la partie VALUES d'une instruction INSERT.
    Gère les lignes multiples: (v1, v2), (v3, v4)
    """
    rows = []
    current_row = []
    current_val = []
    in_string = False
    escape = False
    in_row = False
    
    i = 0
    while i < len(values_str):
        c = values_str[i]
        
        if not in_row:
            if c == '(':
                in_row = True
                current_row = []
                current_val = []
            i += 1
            continue
            
        if in_string:
            if escape:
                current_val.append(c)
                escape = False
            elif c == '\\':
                escape = True
                current_val.append(c)
            elif c == "'":
                # SQL escape style '' (rare dans MariaDB mais possible)
                if i + 1 < len(values_str) and values_str[i+1] == "'":
                    current_val.append("'")
                    i += 1
                else:
                    in_string = False
                    current_val.append(c)
            else:
                current_val.append(c)
        else:
            if c == "'":
                in_string = True
                current_val.append(c)
            elif c == ',':
                rows_val = "".join(current_val).strip()
                current_row.append(rows_val)
                current_val = []
            elif c == ')':
                rows_val = "".join(current_val).strip()
                current_row.append(rows_val)
                rows.append(current_row)
                in_row = False
                current_val = []
            else:
                current_val.append(c)
        i += 1
    return rows

def clean_value(val):
    """Nettoie et convertit une valeur SQL en type Python."""
    val = val.strip()
    if val.upper() == 'NULL':
        return None
    if val.startswith("'") and val.endswith("'"):
        s = val[1:-1]
        # Unescaping MariaDB
        s = s.replace("\\'", "'").replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\\\', '\\')
        
        # Correction pour les dates naïves (ajoute le fuseau horaire UTC)
        if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$', s):
            return s + "Z"
            
        return s
    
    # Nombres
    if val.isdigit():
        return int(val)
    if val.lower() == 'true': return True
    if val.lower() == 'false': return False
    
    try:
        if '.' in val or 'e' in val.lower():
            return float(val)
    except ValueError:
        pass
    
    return val

def extract_table_info(sql_content):
    """Extrait les colonnes et la clé primaire de chaque CREATE TABLE."""
    table_info = {}
    # Pattern pour capturer CREATE TABLE `table_name` ( ... )
    create_pattern = re.compile(r'CREATE TABLE `([^`]+)` \((.*?)\) ENGINE', re.DOTALL)
    
    for table_name, body in create_pattern.findall(sql_content):
        cols = []
        pk = None
        for line in body.strip().split('\n'):
            line = line.strip()
            if line.startswith('`'):
                col_match = re.search(r'`([^`]+)`', line)
                if col_match:
                    cols.append(col_match.group(1))
            if 'PRIMARY KEY' in line:
                pk_match = re.search(r'PRIMARY KEY \(`([^`]+)`\)', line)
                if pk_match:
                    pk = pk_match.group(1)
        
        table_info[table_name] = {'columns': cols, 'pk': pk}
    return table_info

def get_django_model(table_name):
    """Détermine le nom du modèle Django à partir du nom de la table."""
    if table_name in TABLE_TO_MODEL:
        return TABLE_TO_MODEL[table_name]
    
    # Pattern par défaut: appname_modelname -> appname.modelname
    if '_' in table_name:
        parts = table_name.split('_')
        return f"{parts[0]}.{'_'.join(parts[1:])}"
    
    return f"unknown.{table_name}"

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_mariadb_to_fixture.py <sql_file> [output_file]")
        sys.exit(1)
        
    sql_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('mariadb_fixture.json')
    
    if not sql_path.exists():
        print(f"Erreur: Fichier {sql_path} non trouvé")
        sys.exit(1)
        
    print(f"Lecture de {sql_path}...")
    # On utilise errors='ignore' pour les caractères mal encodés dans les dumps volumineux
    with open(sql_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    print("Analyse de la structure des tables...")
    table_info = extract_table_info(content)
    print(f"Trouvé {len(table_info)} définitions de tables.")
    
    fixture = []
    
    # Extraction des INSERT INTO
    # On cherche INSERT INTO `table` VALUES (...);
    insert_pattern = re.compile(r'INSERT INTO `([^`]+)` VALUES (.*?);', re.DOTALL)
    
    print("Conversion des données...")
    inserts = insert_pattern.findall(content)
    print(f"Trouvé {len(inserts)} instructions INSERT.")
    
    for table_name, values_str in inserts:
        if table_name in TABLES_TO_IGNORE:
            continue
            
        if table_name not in table_info:
            print(f"Attention: Table {table_name} non définie dans CREATE TABLE. Tentative d'inférence...")
            continue
            
        model = get_django_model(table_name)
        info = table_info[table_name]
        cols = info['columns']
        pk_col = info['pk'] or (cols[0] if cols else 'id')
        
        rows = parse_sql_values(values_str)
        for row in rows:
            if len(row) != len(cols):
                # Parfois MariaDB n'inclut pas toutes les colonnes s'il y a des valeurs par défaut
                # Mais les dumps standards incluent tout dans l'ordre du CREATE TABLE
                continue
                
            fields = {}
            pk_value = None
            
            # Récupérer les renommages pour cette table
            table_field_mapping = FIELD_MAPPINGS.get(table_name, {})
            
            for i, val_str in enumerate(row):
                col_name = cols[i]
                val = clean_value(val_str)
                
                # Appliquer le renommage si nécessaire
                target_field_name = table_field_mapping.get(col_name, col_name)
                
                if target_field_name is None:
                    continue # Champ à ignorer
                
                # Nettoyage spécifique pour les avatars si on est dans users_profile
                if table_name == 'users_profile' and target_field_name == 'avatar':
                    if val and val.startswith('static/uploads/'):
                        val = val.replace('static/uploads/', '')
                
                if col_name == pk_col or target_field_name == 'pk':
                    pk_value = val
                else:
                    fields[target_field_name] = val
            
            # Appliquer les valeurs par défaut pour les champs manquants
            if '__defaults__' in table_field_mapping:
                for def_field, def_val in table_field_mapping['__defaults__'].items():
                    if def_field not in fields:
                        fields[def_field] = def_val
            
            fixture.append({
                "model": model,
                "pk": pk_value,
                "fields": fields
            })
            
    print(f"Sauvegarde de {len(fixture)} enregistrements dans {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)
        
    print("\nSuccès ! Fixture créée.")
    print(f"Pour charger les données : python manage.py loaddata {output_path}")
    print("\nNote: Vous devrez peut-être adapter le dictionnaire TABLE_TO_MODEL")
    print("      dans le script si certains noms de modèles ne correspondent pas.")

if __name__ == '__main__':
    main()
