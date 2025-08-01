#!/usr/bin/env python3

import os
import re

def fix_database_types(file_path):
    """Supprimer les type hints Database des paramètres de fonction"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remplacer db: Database = par db = 
    pattern = r'db: Database = '
    replacement = 'db = '
    content = re.sub(pattern, replacement, content)
    
    # Supprimer l'import Database s'il n'est plus utilisé que pour les type hints
    # Garder seulement si utilisé ailleurs
    if 'Database' not in content.replace('from ...core.database import Database', ''):
        content = re.sub(r'from \.\.\.core\.database import Database\n', '', content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Corrigé: {file_path}")

# Liste des fichiers à corriger
files_to_fix = [
    '/app/backend/app/api/endpoints/users.py',
    '/app/backend/app/api/endpoints/channels.py', 
    '/app/backend/app/api/endpoints/messages.py',
    '/app/backend/app/api/endpoints/servers.py',
    '/app/backend/app/api/endpoints/federation.py',
    '/app/backend/app/sse/events.py'
]

for file_path in files_to_fix:
    if os.path.exists(file_path):
        fix_database_types(file_path)
    else:
        print(f"Fichier non trouvé: {file_path}")

print("Correction des types Database terminée!")