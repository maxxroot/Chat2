"""
Gestionnaire de base de données MongoDB avec support pour la fédération
"""

from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
from .config import settings

class Database:
    def __init__(self, client: AsyncIOMotorClient):
        self.client = client
        self.db: AsyncIOMotorDatabase = client[settings.DATABASE_NAME]
        
        # Collections principales
        self.users = self.db.users
        self.servers = self.db.servers
        self.channels = self.db.channels
        self.messages = self.db.messages
        self.sessions = self.db.sessions
        self.relationships = self.db.relationships
        
        # Collections pour la fédération
        self.federation_instances = self.db.federation_instances
        self.activitypub_actors = self.db.activitypub_actors
        self.activitypub_activities = self.db.activitypub_activities
        self.remote_users = self.db.remote_users
        self.remote_servers = self.db.remote_servers
    
    async def initialize_indexes(self):
        """Créer les index nécessaires pour les performances"""
        
        # Index pour les utilisateurs
        await self.users.create_indexes([
            IndexModel([("username", ASCENDING)], unique=True),
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("federation.actor_id", ASCENDING)], sparse=True),
            IndexModel([("created_at", DESCENDING)])
        ])
        
        # Index pour les serveurs
        await self.servers.create_indexes([
            IndexModel([("name", TEXT)]),
            IndexModel([("owner_id", ASCENDING)]),
            IndexModel([("federation.actor_id", ASCENDING)], sparse=True),
            IndexModel([("created_at", DESCENDING)])
        ])
        
        # Index pour les canaux
        await self.channels.create_indexes([
            IndexModel([("server_id", ASCENDING)]),
            IndexModel([("name", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)])
        ])
        
        # Index pour les messages
        await self.messages.create_indexes([
            IndexModel([("channel_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("author_id", ASCENDING)]),
            IndexModel([("federation.activity_id", ASCENDING)], sparse=True),
            IndexModel([("content", TEXT)])
        ])
        
        # Index pour les sessions
        await self.sessions.create_indexes([
            IndexModel([("token", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("expires_at", ASCENDING)])
        ])
        
        # Index pour la fédération
        await self.federation_instances.create_indexes([
            IndexModel([("domain", ASCENDING)], unique=True),
            IndexModel([("status", ASCENDING)])
        ])
        
        await self.activitypub_actors.create_indexes([
            IndexModel([("actor_id", ASCENDING)], unique=True),
            IndexModel([("preferred_username", ASCENDING)]),
            IndexModel([("domain", ASCENDING)])
        ])
        
        await self.activitypub_activities.create_indexes([
            IndexModel([("activity_id", ASCENDING)], unique=True),
            IndexModel([("type", ASCENDING)]),
            IndexModel([("actor", ASCENDING)]),
            IndexModel([("published", DESCENDING)])
        ])
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un utilisateur par son ID"""
        return await self.users.find_one({"_id": user_id})
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Récupérer un utilisateur par son nom d'utilisateur"""
        return await self.users.find_one({"username": username})
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Récupérer un utilisateur par son email"""
        return await self.users.find_one({"email": email})
    
    async def create_user(self, user_data: Dict[str, Any]) -> str:
        """Créer un nouvel utilisateur"""
        result = await self.users.insert_one(user_data)
        return str(result.inserted_id)
    
    async def get_server_by_id(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un serveur par son ID"""
        return await self.servers.find_one({"_id": server_id})
    
    async def get_servers_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les serveurs d'un utilisateur"""
        return await self.servers.find({
            "$or": [
                {"owner_id": user_id},
                {"members": user_id}
            ]
        }).to_list(None)
    
    async def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un canal par son ID"""
        return await self.channels.find_one({"_id": channel_id})
    
    async def get_channels_by_server(self, server_id: str) -> List[Dict[str, Any]]:
        """Récupérer tous les canaux d'un serveur"""
        return await self.channels.find({"server_id": server_id}).to_list(None)
    
    async def get_messages_by_channel(self, channel_id: str, limit: int = 50, before: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupérer les messages d'un canal"""
        query = {"channel_id": channel_id}
        if before:
            query["_id"] = {"$lt": before}
        
        return await self.messages.find(query).sort("created_at", DESCENDING).limit(limit).to_list(None)
    
    async def create_message(self, message_data: Dict[str, Any]) -> str:
        """Créer un nouveau message"""
        result = await self.messages.insert_one(message_data)
        return str(result.inserted_id)
    
    # Méthodes spécifiques à la fédération
    
    async def get_federation_instance(self, domain: str) -> Optional[Dict[str, Any]]:
        """Récupérer une instance fédérée par son domaine"""
        return await self.federation_instances.find_one({"domain": domain})
    
    async def register_federation_instance(self, instance_data: Dict[str, Any]) -> str:
        """Enregistrer une nouvelle instance fédérée"""
        result = await self.federation_instances.insert_one(instance_data)
        return str(result.inserted_id)
    
    async def get_activitypub_actor_by_id(self, actor_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un acteur ActivityPub par son ID"""
        return await self.activitypub_actors.find_one({"actor_id": actor_id})
    
    async def store_activitypub_activity(self, activity_data: Dict[str, Any]) -> str:
        """Stocker une activité ActivityPub"""
        result = await self.activitypub_activities.insert_one(activity_data)
        return str(result.inserted_id)
    
    async def get_remote_user_by_actor_id(self, actor_id: str) -> Optional[Dict[str, Any]]:
        """Récupérer un utilisateur distant par son actor_id ActivityPub"""
        return await self.remote_users.find_one({"federation.actor_id": actor_id})