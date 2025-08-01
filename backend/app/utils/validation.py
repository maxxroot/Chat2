"""
Utilitaires de validation
"""

import re
from typing import Optional

# Expressions régulières pour la validation
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{2,32}$")
DISPLAY_NAME_REGEX = re.compile(r"^[^\n\r\u200B]{2,32}$")
SERVER_NAME_REGEX = re.compile(r"^[^\n\r\u200B]{1,32}$")
CHANNEL_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

def validate_username(username: str) -> bool:
    """Valider un nom d'utilisateur"""
    return bool(USERNAME_REGEX.match(username))

def validate_display_name(display_name: str) -> bool:
    """Valider un nom d'affichage"""
    return bool(DISPLAY_NAME_REGEX.match(display_name))

def validate_server_name(name: str) -> bool:
    """Valider un nom de serveur"""
    return bool(SERVER_NAME_REGEX.match(name))

def validate_channel_name(name: str) -> bool:
    """Valider un nom de canal"""
    return bool(CHANNEL_NAME_REGEX.match(name))

def validate_discriminator(discriminator: str) -> bool:
    """Valider un discriminateur"""
    return len(discriminator) == 4 and discriminator.isdigit()

def clean_content(content: str) -> str:
    """Nettoyer le contenu d'un message"""
    # Supprimer les caractères de contrôle dangereux
    cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', content)
    
    # Limiter les sauts de ligne consécutifs
    cleaned = re.sub(r'\n{4,}', '\n\n\n', cleaned)
    
    return cleaned.strip()

def extract_mentions(content: str) -> list:
    """Extraire les mentions d'un contenu"""
    mentions = []
    
    # Mentions d'utilisateurs @username
    user_mentions = re.findall(r'@([a-zA-Z0-9_.-]+)', content)
    for username in user_mentions:
        mentions.append({
            "type": "user",
            "id": username
        })
    
    # Mentions de canaux #channel
    channel_mentions = re.findall(r'#([a-zA-Z0-9_-]+)', content)
    for channel_name in channel_mentions:
        mentions.append({
            "type": "channel", 
            "id": channel_name
        })
    
    return mentions

def is_valid_nanoid(nanoid: str) -> bool:
    """Vérifier si une chaîne est un nanoid valide"""
    if not nanoid or len(nanoid) != 21:
        return False
    
    # Les nanoids utilisent ces caractères
    valid_chars = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-")
    return all(c in valid_chars for c in nanoid)

def sanitize_filename(filename: str) -> str:
    """Sécuriser un nom de fichier"""
    # Supprimer les caractères dangereux
    sanitized = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limiter la longueur
    if len(sanitized) > 100:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:95] + ('.' + ext if ext else '')
    
    return sanitized