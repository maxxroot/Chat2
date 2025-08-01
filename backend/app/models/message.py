"""
Modèles de données pour les messages avec support de fédération
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class MessageType(str, Enum):
    TEXT = "text"
    USER_ADDED = "user_added"
    USER_REMOVE = "user_remove"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_KICKED = "user_kicked"
    USER_BANNED = "user_banned"
    CHANNEL_RENAMED = "channel_renamed"
    CHANNEL_DESCRIPTION_CHANGED = "channel_description_changed"
    CHANNEL_ICON_CHANGED = "channel_icon_changed"

class MessageFederation(BaseModel):
    """Données de fédération pour un message"""
    activity_id: Optional[str] = None  # ID de l'activité ActivityPub
    note_id: Optional[str] = None      # ID de la Note ActivityPub
    origin_domain: Optional[str] = None
    is_remote: bool = False

class MessageAttachment(BaseModel):
    """Pièce jointe d'un message"""
    id: str
    filename: str
    size: int
    content_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    url: str

class MessageEmbed(BaseModel):
    """Embed d'un message"""
    type: str = "rich"
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    colour: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    # Médias
    image: Optional[Dict[str, Any]] = None
    thumbnail: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None
    
    # Auteur et footer
    author: Optional[Dict[str, Any]] = None
    footer: Optional[Dict[str, Any]] = None
    
    # Champs
    fields: List[Dict[str, Any]] = []

class MessageReaction(BaseModel):
    """Réaction à un message"""
    emoji_id: str  # ID de l'emoji ou caractère Unicode
    user_ids: List[str] = []

class MessageMention(BaseModel):
    """Mention dans un message"""
    id: str
    type: str  # "user", "channel", "role"

class Message(BaseModel):
    """Modèle message principal"""
    id: str = Field(alias="_id")
    channel_id: str
    author_id: str
    content: Optional[str] = Field(None, max_length=2000)
    message_type: MessageType = MessageType.TEXT
    
    # Contenu enrichi
    attachments: List[MessageAttachment] = []
    embeds: List[MessageEmbed] = []
    mentions: List[MessageMention] = []
    reactions: List[MessageReaction] = []
    
    # Métadonnées
    created_at: datetime
    updated_at: Optional[datetime] = None
    edited_at: Optional[datetime] = None
    
    # Message parent (pour les réponses)
    reply_to: Optional[str] = None
    
    # Fédération
    federation: Optional[MessageFederation] = None
    
    class Config:
        populate_by_name = True

class MessageCreate(BaseModel):
    """Données pour créer un message"""
    content: Optional[str] = Field(None, max_length=2000)
    attachments: List[str] = []  # IDs des fichiers uploadés
    reply_to: Optional[str] = None
    
    class Config:
        # Au moins content ou attachments requis
        @classmethod
        def __get_validators__(cls):
            yield cls.validate_content_or_attachments
        
        @classmethod
        def validate_content_or_attachments(cls, v):
            if not v.content and not v.attachments:
                raise ValueError("Le message doit avoir du contenu ou des pièces jointes")
            return v

class MessageUpdate(BaseModel):
    """Données pour mettre à jour un message"""
    content: Optional[str] = Field(None, max_length=2000)

class MessageResponse(BaseModel):
    """Réponse message"""
    id: str
    channel_id: str
    author_id: str
    content: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    attachments: List[MessageAttachment] = []
    embeds: List[MessageEmbed] = []
    mentions: List[MessageMention] = []
    reactions: List[MessageReaction] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    edited_at: Optional[datetime] = None
    reply_to: Optional[str] = None
    federation: Optional[MessageFederation] = None

class MessageSearchQuery(BaseModel):
    """Requête de recherche de messages"""
    query: str = Field(min_length=1, max_length=100)
    channel_id: Optional[str] = None
    author_id: Optional[str] = None
    before: Optional[datetime] = None
    after: Optional[datetime] = None
    limit: int = Field(default=50, le=100)

class MessageBulkDelete(BaseModel):
    """Suppression en masse de messages"""
    message_ids: List[str] = Field(min_items=1, max_items=100)