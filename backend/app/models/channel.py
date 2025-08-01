"""
Modèles de données pour les canaux
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class ChannelType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    DM = "dm"
    GROUP = "group"

class Channel(BaseModel):
    """Modèle canal principal"""
    id: str = Field(alias="_id")
    channel_type: ChannelType
    name: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=1024)
    
    # Serveur parent (None pour DM/Group)
    server_id: Optional[str] = None
    
    # Pour les canaux DM/Group
    recipients: List[str] = []  # IDs des utilisateurs
    
    # Médias
    icon: Optional[str] = None  # ID du fichier icône
    
    # Configuration
    nsfw: bool = False
    
    # Dernier message
    last_message_id: Optional[str] = None
    last_message_at: Optional[datetime] = None
    
    # Métadonnées
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True

class ChannelCreate(BaseModel):
    """Données pour créer un canal"""
    channel_type: ChannelType
    name: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=1024)
    nsfw: bool = False
    
    # Pour les canaux DM/Group
    recipients: List[str] = []

class ChannelUpdate(BaseModel):
    """Données pour mettre à jour un canal"""
    name: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=1024)
    icon: Optional[str] = None
    nsfw: Optional[bool] = None

class ChannelResponse(BaseModel):
    """Réponse canal"""
    id: str
    channel_type: ChannelType
    name: Optional[str] = None
    description: Optional[str] = None
    server_id: Optional[str] = None
    recipients: List[str] = []
    icon: Optional[str] = None
    nsfw: bool = False
    last_message_id: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Champs calculés
    message_count: int = 0