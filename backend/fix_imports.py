#!/usr/bin/env python3

import os
import re

def fix_imports_and_dependencies(file_path):
    """Fixer les imports et supprimer les fonctions get_db locales"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Ajouter l'import de get_db depuis dependencies si pas présent
    if 'from ..dependencies import get_db' not in content:
        # Trouver la dernière ligne d'import local
        lines = content.split('\n')
        insert_index = -1
        
        for i, line in enumerate(lines):
            if line.startswith('from ...') and 'import' in line:
                insert_index = i
        
        if insert_index >= 0:
            lines.insert(insert_index + 1, 'from ..dependencies import get_db')
            content = '\n'.join(lines)
    
    # Supprimer les fonctions get_db locales
    pattern = r'async def get_db\(\).*?\n    return.*?\n\n'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    # Aussi supprimer les versions avec type hints
    pattern = r'async def get_db\(\) -> .*?\n    """.*?"""\n.*?\n    return.*?\n\n'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Imports corrigés: {file_path}")

# Fichiers à corriger (sauf auth.py qui est déjà fait)
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
        fix_imports_and_dependencies(file_path)
    else:
        print(f"Fichier non trouvé: {file_path}")

print("Correction des imports terminée!")