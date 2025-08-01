"""
Modèles de données pour les serveurs avec support de fédération
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class ServerFederation(BaseModel):
    """Données de fédération pour un serveur"""
    actor_id: Optional[str] = None  # URL de l'acteur ActivityPub (Group)
    domain: Optional[str] = None    # Domaine de l'instance d'origine
    inbox_url: Optional[str] = None
    outbox_url: Optional[str] = None
    following_url: Optional[str] = None
    followers_url: Optional[str] = None
    public_key: Optional[str] = None
    is_remote: bool = False

class ServerFlags(str, Enum):
    VERIFIED = "verified"
    OFFICIAL = "official"
    NSFW = "nsfw"

class SystemMessageChannels(BaseModel):
    """Configuration des canaux système"""
    user_joined: Optional[str] = None
    user_left: Optional[str] = None
    user_kicked: Optional[str] = None
    user_banned: Optional[str] = None

class Server(BaseModel):
    """Modèle serveur principal"""
    id: str = Field(alias="_id")
    name: str = Field(min_length=1, max_length=32)
    description: Optional[str] = Field(None, max_length=1024)
    
    # Propriétaire et membres
    owner_id: str
    members: List[str] = []  # IDs des membres
    
    # Médias
    icon: Optional[str] = None    # ID du fichier icône
    banner: Optional[str] = None  # ID du fichier bannière
    
    # Configuration
    nsfw: bool = False
    discoverable: bool = True
    analytics: bool = False
    
    # Canaux système
    system_messages: Optional[SystemMessageChannels] = None
    
    # Drapeaux
    flags: List[ServerFlags] = []
    
    # Métadonnées
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Fédération
    federation: Optional[ServerFederation] = None
    
    class Config:
        populate_by_name = True

class ServerCreate(BaseModel):
    """Données pour créer un serveur"""
    name: str = Field(min_length=1, max_length=32)
    description: Optional[str] = Field(None, max_length=1024)
    nsfw: bool = False
    discoverable: bool = True

class ServerUpdate(BaseModel):
    """Données pour mettre à jour un serveur"""
    name: Optional[str] = Field(None, min_length=1, max_length=32)
    description: Optional[str] = Field(None, max_length=1024)
    icon: Optional[str] = None
    banner: Optional[str] = None
    nsfw: Optional[bool] = None
    discoverable: Optional[bool] = None
    analytics: Optional[bool] = None
    system_messages: Optional[SystemMessageChannels] = None

class ServerResponse(BaseModel):
    """Réponse serveur"""
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    icon: Optional[str] = None
    banner: Optional[str] = None
    nsfw: bool = False
    discoverable: bool = True
    analytics: bool = False
    system_messages: Optional[SystemMessageChannels] = None
    flags: List[ServerFlags] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    federation: Optional[ServerFederation] = None
    
    # Champs calculés
    member_count: int = 0
    channel_count: int = 0

class ServerMember(BaseModel):
    """Membre d'un serveur"""
    id: str = Field(alias="_id")  # Combinaison server_id:user_id
    server_id: str
    user_id: str
    nickname: Optional[str] = Field(None, max_length=32)
    avatar: Optional[str] = None  # Avatar spécifique au serveur
    roles: List[str] = []  # IDs des rôles
    joined_at: datetime
    
    class Config:
        populate_by_name = True

class ServerBan(BaseModel):
    """Bannissement d'un serveur"""
    id: str = Field(alias="_id")  # Combinaison server_id:user_id
    server_id: str
    user_id: str
    reason: Optional[str] = Field(None, max_length=1024)
    banned_by: str  # ID du modérateur
    banned_at: datetime
    
    class Config:
        populate_by_name = True

class ServerInvite(BaseModel):
    """Invitation à un serveur"""
    id: str = Field(alias="_id")
    server_id: str
    channel_id: str
    creator_id: str
    code: str = Field(min_length=8, max_length=8)
    uses: int = 0
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True

class ServerInviteCreate(BaseModel):
    """Données pour créer une invitation"""
    channel_id: str
    max_uses: Optional[int] = None
    expires_in: Optional[int] = None  # Secondes

class ServerInviteResponse(BaseModel):
    """Réponse invitation"""
    code: str
    server_id: str
    channel_id: str
    uses: int
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime