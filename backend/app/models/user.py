"""
Modèles de données pour les utilisateurs avec support de fédération
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from enum import Enum

class UserStatus(str, Enum):
    ONLINE = "online"
    IDLE = "idle"
    FOCUS = "focus"
    BUSY = "busy"
    INVISIBLE = "invisible"

class RelationshipStatus(str, Enum):
    NONE = "none"
    FRIEND = "friend"
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BLOCKED = "blocked"
    BLOCKED_OTHER = "blocked_other"

class UserBadges(str, Enum):
    DEVELOPER = "developer"
    TRANSLATOR = "translator"
    SUPPORTER = "supporter"
    FOUNDER = "founder"
    MODERATOR = "moderator"

class UserFlags(str, Enum):
    SUSPENDED = "suspended"
    DELETED = "deleted"
    BANNED = "banned"
    SPAM = "spam"

class UserFederation(BaseModel):
    """Données de fédération pour un utilisateur"""
    actor_id: Optional[str] = None  # URL de l'acteur ActivityPub
    domain: Optional[str] = None    # Domaine de l'instance d'origine
    inbox_url: Optional[str] = None
    outbox_url: Optional[str] = None
    following_url: Optional[str] = None
    followers_url: Optional[str] = None
    public_key: Optional[str] = None
    is_remote: bool = False

class UserProfile(BaseModel):
    """Profil utilisateur"""
    content: Optional[str] = Field(None, max_length=2000)
    background: Optional[str] = None  # ID du fichier de fond

class UserStatusInfo(BaseModel):
    """Statut utilisateur détaillé"""
    text: Optional[str] = Field(None, max_length=128)
    presence: Optional[UserStatus] = UserStatus.ONLINE

class Relationship(BaseModel):
    """Relation entre utilisateurs"""
    user_id: str
    status: RelationshipStatus

class User(BaseModel):
    """Modèle utilisateur principal"""
    id: str = Field(alias="_id")
    username: str = Field(min_length=2, max_length=32)
    discriminator: str = Field(default="0001")
    display_name: Optional[str] = Field(None, max_length=32)
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None  # ID du fichier avatar
    banner: Optional[str] = None  # ID du fichier bannière
    
    # Statut et présence
    status: Optional[UserStatusInfo] = None
    
    # Relations
    relationships: List[Relationship] = []
    
    # Badges et drapeaux
    badges: List[UserBadges] = []
    flags: List[UserFlags] = []
    
    # Permissions
    privileged: bool = False
    
    # Profil
    profile: Optional[UserProfile] = None
    
    # Métadonnées
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    
    # Fédération
    federation: Optional[UserFederation] = None
    
    # Champs calculés (ne sont pas stockés)
    online: bool = False
    relationship: RelationshipStatus = RelationshipStatus.NONE
    
    class Config:
        populate_by_name = True

class UserCreate(BaseModel):
    """Données pour créer un utilisateur"""
    username: str = Field(min_length=2, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=32)

class UserUpdate(BaseModel):
    """Données pour mettre à jour un utilisateur"""
    display_name: Optional[str] = Field(None, max_length=32)
    avatar: Optional[str] = None
    banner: Optional[str] = None
    status: Optional[UserStatusInfo] = None
    profile: Optional[UserProfile] = None

class UserLogin(BaseModel):
    """Données de connexion"""
    login: str  # username ou email
    password: str

class UserResponse(BaseModel):
    """Réponse utilisateur (sans données sensibles)"""
    id: str
    username: str
    discriminator: str
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    banner: Optional[str] = None
    status: Optional[UserStatusInfo] = None
    badges: List[UserBadges] = []
    flags: List[UserFlags] = []
    privileged: bool = False
    created_at: datetime
    last_active: Optional[datetime] = None
    federation: Optional[UserFederation] = None
    online: bool = False
    relationship: RelationshipStatus = RelationshipStatus.NONE

class UserWithToken(BaseModel):
    """Utilisateur avec token d'authentification"""
    user: UserResponse
    token: str
    expires_at: datetime