"""
Gestionnaire de fédération ActivityPub pour Revolt
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from .config import settings
from .database import Database

class FederationManager:
    def __init__(self, domain: str, name: str, description: str):
        self.domain = domain
        self.name = name
        self.description = description
        self.public_key = None
        self.private_key = None
        self.known_instances: Dict[str, Dict] = {}
        
        # Générer les clés RSA pour la signature des activités
        self._generate_keypair()
    
    def _generate_keypair(self):
        """Générer une paire de clés RSA pour la signature ActivityPub"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        self.private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_key = private_key.public_key()
        self.public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def get_actor_url(self, username: str) -> str:
        """Construire l'URL d'un acteur local"""
        return f"https://{self.domain}/api/activitypub/users/{username}"
    
    def get_object_url(self, object_type: str, object_id: str) -> str:
        """Construire l'URL d'un objet local"""
        return f"https://{self.domain}/api/activitypub/{object_type}/{object_id}"
    
    async def create_actor(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Créer un acteur ActivityPub pour un utilisateur local"""
        username = user_data["username"]
        display_name = user_data.get("display_name", username)
        
        actor = {
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                "https://w3id.org/security/v1"
            ],
            "type": "Person",
            "id": self.get_actor_url(username),
            "preferredUsername": username,
            "name": display_name,
            "summary": user_data.get("bio", ""),
            "inbox": f"https://{self.domain}/api/activitypub/users/{username}/inbox",
            "outbox": f"https://{self.domain}/api/activitypub/users/{username}/outbox",
            "followers": f"https://{self.domain}/api/activitypub/users/{username}/followers",
            "following": f"https://{self.domain}/api/activitypub/users/{username}/following",
            "publicKey": {
                "id": f"{self.get_actor_url(username)}#main-key",
                "owner": self.get_actor_url(username),
                "publicKeyPem": self.public_key
            },
            "endpoints": {
                "sharedInbox": f"https://{self.domain}/api/activitypub/inbox"
            },
            "published": user_data.get("created_at", datetime.now(timezone.utc)).isoformat()
        }
        
        if "avatar" in user_data:
            actor["icon"] = {
                "type": "Image",
                "url": f"https://{self.domain}/uploads/{user_data['avatar']}"
            }
        
        return actor
    
    async def create_group_actor(self, server_data: Dict[str, Any]) -> Dict[str, Any]:
        """Créer un acteur ActivityPub pour un serveur local (Group)"""
        server_id = server_data["_id"]
        name = server_data["name"]
        
        actor = {
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                "https://w3id.org/security/v1"
            ],
            "type": "Group",
            "id": self.get_object_url("servers", server_id),
            "preferredUsername": server_id,
            "name": name,
            "summary": server_data.get("description", ""),
            "inbox": f"https://{self.domain}/api/activitypub/servers/{server_id}/inbox",
            "outbox": f"https://{self.domain}/api/activitypub/servers/{server_id}/outbox",
            "followers": f"https://{self.domain}/api/activitypub/servers/{server_id}/followers",
            "following": f"https://{self.domain}/api/activitypub/servers/{server_id}/following",
            "publicKey": {
                "id": f"{self.get_object_url('servers', server_id)}#main-key",
                "owner": self.get_object_url("servers", server_id),
                "publicKeyPem": self.public_key
            },
            "endpoints": {
                "sharedInbox": f"https://{self.domain}/api/activitypub/inbox"
            },
            "published": server_data.get("created_at", datetime.now(timezone.utc)).isoformat()
        }
        
        if "icon" in server_data:
            actor["icon"] = {
                "type": "Image",
                "url": f"https://{self.domain}/uploads/{server_data['icon']}"
            }
        
        return actor
    
    async def create_note_activity(self, message_data: Dict[str, Any], author_username: str) -> Dict[str, Any]:
        """Créer une activité Note ActivityPub pour un message"""
        message_id = message_data["_id"]
        content = message_data["content"]
        
        note = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "id": self.get_object_url("messages", message_id),
            "attributedTo": self.get_actor_url(author_username),
            "content": content,
            "published": message_data.get("created_at", datetime.now(timezone.utc)).isoformat(),
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": []
        }
        
        # Ajouter les pièces jointes si présentes
        if "attachments" in message_data and message_data["attachments"]:
            note["attachment"] = []
            for attachment in message_data["attachments"]:
                note["attachment"].append({
                    "type": "Document",
                    "mediaType": attachment.get("content_type", "application/octet-stream"),
                    "url": f"https://{self.domain}/uploads/{attachment['filename']}"
                })
        
        return note
    
    async def create_activity(self, activity_type: str, actor_url: str, object_data: Dict[str, Any]) -> Dict[str, Any]:
        """Créer une activité ActivityPub générique"""
        activity_id = f"https://{self.domain}/api/activitypub/activities/{activity_type.lower()}-{datetime.now().timestamp()}"
        
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": activity_type,
            "id": activity_id,
            "actor": actor_url,
            "object": object_data,
            "published": datetime.now(timezone.utc).isoformat()
        }
        
        return activity
    
    async def discover_instance(self, domain: str) -> Optional[Dict[str, Any]]:
        """Découvrir une instance fédérée via NodeInfo"""
        try:
            async with httpx.AsyncClient() as client:
                # Étape 1: Récupérer .well-known/nodeinfo
                nodeinfo_response = await client.get(f"https://{domain}/.well-known/nodeinfo")
                if nodeinfo_response.status_code != 200:
                    return None
                
                nodeinfo_data = nodeinfo_response.json()
                
                # Étape 2: Récupérer les informations détaillées
                nodeinfo_url = None
                for link in nodeinfo_data.get("links", []):
                    if "nodeinfo.diaspora.software/ns/schema/2.0" in link.get("rel", ""):
                        nodeinfo_url = link["href"]
                        break
                
                if not nodeinfo_url:
                    return None
                
                detailed_response = await client.get(nodeinfo_url)
                if detailed_response.status_code != 200:
                    return None
                
                instance_info = detailed_response.json()
                
                # Stocker les informations de l'instance
                return {
                    "domain": domain,
                    "software": instance_info.get("software", {}),
                    "protocols": instance_info.get("protocols", []),
                    "metadata": instance_info.get("metadata", {}),
                    "discovered_at": datetime.now(timezone.utc),
                    "status": "active"
                }
        
        except Exception as e:
            print(f"Erreur lors de la découverte de l'instance {domain}: {e}")
            return None
    
    async def fetch_actor(self, actor_url: str) -> Optional[Dict[str, Any]]:
        """Récupérer un acteur distant"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Accept": "application/activity+json, application/ld+json"
                }
                response = await client.get(actor_url, headers=headers)
                
                if response.status_code == 200:
                    return response.json()
                
        except Exception as e:
            print(f"Erreur lors de la récupération de l'acteur {actor_url}: {e}")
            
        return None
    
    async def send_activity_to_inbox(self, inbox_url: str, activity: Dict[str, Any]) -> bool:
        """Envoyer une activité à la boîte de réception d'un acteur distant"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Content-Type": "application/activity+json",
                    "Accept": "application/activity+json"
                }
                
                # TODO: Ajouter la signature HTTP pour l'authentification
                response = await client.post(
                    inbox_url,
                    json=activity,
                    headers=headers
                )
                
                return response.status_code in [200, 201, 202]
                
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'activité à {inbox_url}: {e}")
            return False
    
    async def process_inbox_activity(self, activity: Dict[str, Any], db: Database) -> bool:
        """Traiter une activité reçue dans la boîte de réception"""
        activity_type = activity.get("type")
        
        try:
            if activity_type == "Follow":
                return await self._handle_follow_activity(activity, db)
            elif activity_type == "Accept":
                return await self._handle_accept_activity(activity, db)
            elif activity_type == "Create":
                return await self._handle_create_activity(activity, db)
            elif activity_type == "Update":
                return await self._handle_update_activity(activity, db)
            elif activity_type == "Delete":
                return await self._handle_delete_activity(activity, db)
            else:
                print(f"Type d'activité non supporté: {activity_type}")
                return False
                
        except Exception as e:
            print(f"Erreur lors du traitement de l'activité {activity_type}: {e}")
            return False
    
    async def _handle_follow_activity(self, activity: Dict[str, Any], db: Database) -> bool:
        """Gérer une demande de suivi (Follow)"""
        actor = activity.get("actor")
        object_url = activity.get("object")
        
        # Récupérer l'acteur distant
        remote_actor = await self.fetch_actor(actor)
        if not remote_actor:
            return False
        
        # Stocker la demande de suivi
        # TODO: Implémenter la logique de suivi
        
        # Envoyer une réponse Accept automatiquement (pour l'instant)
        accept_activity = await self.create_activity("Accept", object_url, activity)
        
        # Envoyer l'Accept à l'acteur distant
        inbox_url = remote_actor.get("inbox")
        if inbox_url:
            return await self.send_activity_to_inbox(inbox_url, accept_activity)
        
        return True
    
    async def _handle_accept_activity(self, activity: Dict[str, Any], db: Database) -> bool:
        """Gérer une acceptation de suivi (Accept)"""
        # TODO: Mettre à jour le statut de la relation de suivi
        return True
    
    async def _handle_create_activity(self, activity: Dict[str, Any], db: Database) -> bool:
        """Gérer la création d'un objet (Create)"""
        obj = activity.get("object", {})
        obj_type = obj.get("type")
        
        if obj_type == "Note":
            # Traiter un message distant
            # TODO: Convertir la Note en message Revolt et l'insérer
            pass
        
        return True
    
    async def _handle_update_activity(self, activity: Dict[str, Any], db: Database) -> bool:
        """Gérer la mise à jour d'un objet (Update)"""
        # TODO: Mettre à jour l'objet local correspondant
        return True
    
    async def _handle_delete_activity(self, activity: Dict[str, Any], db: Database) -> bool:
        """Gérer la suppression d'un objet (Delete)"""
        # TODO: Supprimer l'objet local correspondant
        return True