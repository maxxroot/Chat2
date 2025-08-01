"""
Système d'événements Server-Sent Events (SSE) pour les mises à jour temps réel
"""

import json
import asyncio
from typing import Dict, Set, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from sse_starlette.sse import EventSourceResponse
from collections import defaultdict

from ..core.auth import get_current_user
from ..core.database import Database

router = APIRouter()

# Gestionnaire global des connexions SSE
class SSEManager:
    def __init__(self):
        # Connexions par utilisateur
        self.user_connections: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # Connexions par canal
        self.channel_connections: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # Connexions par serveur
        self.server_connections: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # Connexions globales
        self.global_connections: Set[asyncio.Queue] = set()
    
    async def add_user_connection(self, user_id: str, queue: asyncio.Queue):
        """Ajouter une connexion pour un utilisateur"""
        self.user_connections[user_id].add(queue)
    
    async def remove_user_connection(self, user_id: str, queue: asyncio.Queue):
        """Supprimer une connexion utilisateur"""
        self.user_connections[user_id].discard(queue)
        if not self.user_connections[user_id]:
            del self.user_connections[user_id]
    
    async def add_channel_connection(self, channel_id: str, queue: asyncio.Queue):
        """Ajouter une connexion pour un canal"""
        self.channel_connections[channel_id].add(queue)
    
    async def remove_channel_connection(self, channel_id: str, queue: asyncio.Queue):
        """Supprimer une connexion canal"""
        self.channel_connections[channel_id].discard(queue)
        if not self.channel_connections[channel_id]:
            del self.channel_connections[channel_id]
    
    async def add_server_connection(self, server_id: str, queue: asyncio.Queue):
        """Ajouter une connexion pour un serveur"""
        self.server_connections[server_id].add(queue)
    
    async def remove_server_connection(self, server_id: str, queue: asyncio.Queue):
        """Supprimer une connexion serveur"""
        self.server_connections[server_id].discard(queue)
        if not self.server_connections[server_id]:
            del self.server_connections[server_id]
    
    async def broadcast_to_user(self, user_id: str, event_type: str, data: Any):
        """Diffuser un événement à un utilisateur spécifique"""
        if user_id in self.user_connections:
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            dead_queues = set()
            for queue in self.user_connections[user_id]:
                try:
                    await queue.put(event)
                except:
                    dead_queues.add(queue)
            
            # Nettoyer les connexions mortes
            for queue in dead_queues:
                self.user_connections[user_id].discard(queue)
    
    async def broadcast_to_channel(self, channel_id: str, event_type: str, data: Any):
        """Diffuser un événement à tous les abonnés d'un canal"""
        if channel_id in self.channel_connections:
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            dead_queues = set()
            for queue in self.channel_connections[channel_id]:
                try:
                    await queue.put(event)
                except:
                    dead_queues.add(queue)
            
            # Nettoyer les connexions mortes
            for queue in dead_queues:
                self.channel_connections[channel_id].discard(queue)
    
    async def broadcast_to_server(self, server_id: str, event_type: str, data: Any):
        """Diffuser un événement à tous les membres d'un serveur"""
        if server_id in self.server_connections:
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            dead_queues = set()
            for queue in self.server_connections[server_id]:
                try:
                    await queue.put(event)
                except:
                    dead_queues.add(queue)
            
            # Nettoyer les connexions mortes
            for queue in dead_queues:
                self.server_connections[server_id].discard(queue)
    
    async def broadcast_global(self, event_type: str, data: Any):
        """Diffuser un événement global à toutes les connexions"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        dead_queues = set()
        for queue in self.global_connections:
            try:
                await queue.put(event)
            except:
                dead_queues.add(queue)
        
        # Nettoyer les connexions mortes
        for queue in dead_queues:
            self.global_connections.discard(queue)

# Instance globale du gestionnaire SSE
sse_manager = SSEManager()

@router.get("/stream")
async def event_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Flux d'événements SSE pour l'utilisateur connecté"""
    
    async def event_generator():
        queue = asyncio.Queue()
        user_id = current_user["_id"]
        
        try:
            # Ajouter la connexion pour cet utilisateur
            await sse_manager.add_user_connection(user_id, queue)
            
            # Envoyer un événement de connexion
            yield {
                "event": "connected",
                "data": json.dumps({
                    "type": "connection_established",
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
            
            # Boucle de diffusion des événements
            while True:
                try:
                    # Attendre un événement avec timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    yield {
                        "event": event["type"],
                        "data": json.dumps(event)
                    }
                    
                except asyncio.TimeoutError:
                    # Envoyer un ping pour maintenir la connexion
                    yield {
                        "event": "ping",
                        "data": json.dumps({
                            "type": "ping",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
                
                # Vérifier si le client est toujours connecté
                if await request.is_disconnected():
                    break
                    
        except Exception as e:
            print(f"Erreur dans le flux SSE pour l'utilisateur {user_id}: {e}")
        finally:
            # Nettoyer la connexion
            await sse_manager.remove_user_connection(user_id, queue)
    
    return EventSourceResponse(event_generator())

@router.get("/channel/{channel_id}/stream")
async def channel_event_stream(
    channel_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Flux d'événements SSE pour un canal spécifique"""
    
    # Vérifier que l'utilisateur a accès au canal
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Canal introuvable")
    
    # TODO: Vérifier les permissions d'accès au canal
    
    async def event_generator():
        queue = asyncio.Queue()
        user_id = current_user["_id"]
        
        try:
            # Ajouter les connexions
            await sse_manager.add_user_connection(user_id, queue)
            await sse_manager.add_channel_connection(channel_id, queue)
            
            # Envoyer un événement de connexion
            yield {
                "event": "channel_connected",
                "data": json.dumps({
                    "type": "channel_connection_established",
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }
            
            # Boucle de diffusion des événements
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    yield {
                        "event": event["type"],
                        "data": json.dumps(event)
                    }
                    
                except asyncio.TimeoutError:
                    yield {
                        "event": "ping",
                        "data": json.dumps({
                            "type": "ping",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    }
                
                if await request.is_disconnected():
                    break
                    
        except Exception as e:
            print(f"Erreur dans le flux SSE canal {channel_id} pour l'utilisateur {user_id}: {e}")
        finally:
            # Nettoyer les connexions
            await sse_manager.remove_user_connection(user_id, queue)
            await sse_manager.remove_channel_connection(channel_id, queue)
    
    return EventSourceResponse(event_generator())

# Fonctions utilitaires pour déclencher des événements

async def emit_message_created(message_data: dict):
    """Émettre un événement de création de message"""
    await sse_manager.broadcast_to_channel(
        message_data["channel_id"],
        "message_created",
        message_data
    )

async def emit_message_updated(message_data: dict):
    """Émettre un événement de mise à jour de message"""
    await sse_manager.broadcast_to_channel(
        message_data["channel_id"],
        "message_updated",
        message_data
    )

async def emit_message_deleted(channel_id: str, message_id: str):
    """Émettre un événement de suppression de message"""
    await sse_manager.broadcast_to_channel(
        channel_id,
        "message_deleted",
        {"message_id": message_id, "channel_id": channel_id}
    )

async def emit_user_status_changed(user_id: str, status_data: dict):
    """Émettre un événement de changement de statut utilisateur"""
    await sse_manager.broadcast_to_user(
        user_id,
        "user_status_changed",
        {"user_id": user_id, "status": status_data}
    )

async def emit_typing_indicator(channel_id: str, user_id: str, is_typing: bool):
    """Émettre un indicateur de frappe"""
    await sse_manager.broadcast_to_channel(
        channel_id,
        "typing_indicator",
        {
            "channel_id": channel_id,
            "user_id": user_id,
            "is_typing": is_typing
        }
    )

async def emit_server_member_joined(server_id: str, user_id: str):
    """Émettre un événement de membre rejoignant un serveur"""
    await sse_manager.broadcast_to_server(
        server_id,
        "server_member_joined",
        {"server_id": server_id, "user_id": user_id}
    )

async def emit_server_member_left(server_id: str, user_id: str):
    """Émettre un événement de membre quittant un serveur"""
    await sse_manager.broadcast_to_server(
        server_id,
        "server_member_left",
        {"server_id": server_id, "user_id": user_id}
    )