#!/usr/bin/env python3

import os
import re

def fix_database_dependency(file_path):
    """Corriger la signature de get_db dans un fichier"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remplacer la signature de get_db
    pattern = r'async def get_db\(\) -> Database:'
    replacement = 'async def get_db():'
    
    content = re.sub(pattern, replacement, content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Corrigé: {file_path}")

# Liste des fichiers à corriger
files_to_fix = [
    '/app/backend/app/api/endpoints/channels.py',
    '/app/backend/app/api/endpoints/messages.py', 
    '/app/backend/app/api/endpoints/servers.py',
    '/app/backend/app/api/endpoints/federation.py',
    '/app/backend/app/sse/events.py'
]

for file_path in files_to_fix:
    if os.path.exists(file_path):
        fix_database_dependency(file_path)
    else:
        print(f"Fichier non trouvé: {file_path}")

print("Correction terminée!")