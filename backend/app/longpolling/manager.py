"""
Gestionnaire de Long Polling pour les événements temps réel
Alternative au SSE pour les clients qui ne le supportent pas bien
"""

import asyncio
import json
from typing import Dict, Set, Any, Optional, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

class EventType(str, Enum):
    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    MESSAGE_DELETED = "message_deleted"
    USER_STATUS_CHANGED = "user_status_changed"
    TYPING_INDICATOR = "typing_indicator"
    SERVER_MEMBER_JOINED = "server_member_joined"
    SERVER_MEMBER_LEFT = "server_member_left"
    CHANNEL_CREATED = "channel_created"
    CHANNEL_UPDATED = "channel_updated"
    CHANNEL_DELETED = "channel_deleted"

@dataclass
class Event:
    """Événement pour le long polling"""
    id: str
    type: EventType
    data: Any
    timestamp: datetime
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    server_id: Optional[str] = None

class LongPollingManager:
    """Gestionnaire principal du long polling"""
    
    def __init__(self):
        # Files d'événements par utilisateur
        self.user_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Files d'événements par canal
        self.channel_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Files d'événements par serveur
        self.server_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Connexions actives (futures en attente)
        self.user_connections: Dict[str, Set[asyncio.Future]] = defaultdict(set)
        self.channel_connections: Dict[str, Set[asyncio.Future]] = defaultdict(set)
        self.server_connections: Dict[str, Set[asyncio.Future]] = defaultdict(set)
        
        # Dernier ID d'événement par client pour éviter les doublons
        self.last_event_ids: Dict[str, str] = {}
        
        # Lock pour la synchronisation
        self._lock = asyncio.Lock()
    
    async def add_event(self, event: Event):
        """Ajouter un nouvel événement et notifier les clients en attente"""
        async with self._lock:
            # Ajouter l'événement dans les files appropriées
            if event.user_id:
                self.user_events[event.user_id].append(event)
                await self._notify_connections(self.user_connections[event.user_id], event)
            
            if event.channel_id:
                self.channel_events[event.channel_id].append(event)
                await self._notify_connections(self.channel_connections[event.channel_id], event)
            
            if event.server_id:
                self.server_events[event.server_id].append(event)
                await self._notify_connections(self.server_connections[event.server_id], event)
    
    async def _notify_connections(self, connections: Set[asyncio.Future], event: Event):
        """Notifier toutes les connexions en attente avec le nouvel événement"""
        completed_futures = set()
        
        for future in connections:
            if not future.done():
                future.set_result([event])
                completed_futures.add(future)
        
        # Nettoyer les futures complétées
        connections -= completed_futures
    
    async def wait_for_events(
        self,
        user_id: str,
        last_event_id: Optional[str] = None,
        timeout: float = 30.0,
        channels: Optional[List[str]] = None,
        servers: Optional[List[str]] = None
    ) -> List[Event]:
        """
        Attendre de nouveaux événements pour un utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            last_event_id: Dernier ID d'événement reçu par le client
            timeout: Timeout en secondes
            channels: Liste des canaux à écouter
            servers: Liste des serveurs à écouter
        
        Returns:
            Liste des nouveaux événements
        """
        async with self._lock:
            # Récupérer les événements manqués depuis last_event_id
            missed_events = await self._get_missed_events(
                user_id, last_event_id, channels, servers
            )
            
            if missed_events:
                return missed_events
        
        # Créer une future pour attendre de nouveaux événements
        future = asyncio.Future()
        
        try:
            # Ajouter la future aux connexions appropriées
            async with self._lock:
                self.user_connections[user_id].add(future)
                
                if channels:
                    for channel_id in channels:
                        self.channel_connections[channel_id].add(future)
                
                if servers:
                    for server_id in servers:
                        self.server_connections[server_id].add(future)
            
            # Attendre avec timeout
            try:
                events = await asyncio.wait_for(future, timeout=timeout)
                return events
            except asyncio.TimeoutError:
                return []
                
        finally:
            # Nettoyer les connexions
            async with self._lock:
                self.user_connections[user_id].discard(future)
                
                if channels:
                    for channel_id in channels:
                        self.channel_connections[channel_id].discard(future)
                
                if servers:
                    for server_id in servers:
                        self.server_connections[server_id].discard(future)
                
                # Annuler la future si elle n'est pas terminée
                if not future.done():
                    future.cancel()
    
    async def _get_missed_events(
        self,
        user_id: str,
        last_event_id: Optional[str],
        channels: Optional[List[str]],
        servers: Optional[List[str]]
    ) -> List[Event]:
        """Récupérer les événements manqués depuis le dernier ID"""
        if not last_event_id:
            return []
        
        missed_events = []
        
        # Événements utilisateur
        for event in self.user_events[user_id]:
            if event.id > last_event_id:
                missed_events.append(event)
        
        # Événements des canaux
        if channels:
            for channel_id in channels:
                for event in self.channel_events[channel_id]:
                    if event.id > last_event_id and event not in missed_events:
                        missed_events.append(event)
        
        # Événements des serveurs
        if servers:
            for server_id in servers:
                for event in self.server_events[server_id]:
                    if event.id > last_event_id and event not in missed_events:
                        missed_events.append(event)
        
        # Trier par timestamp
        missed_events.sort(key=lambda e: e.timestamp)
        
        return missed_events
    
    async def cleanup_old_events(self, max_age_hours: int = 24):
        """Nettoyer les anciens événements"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        async with self._lock:
            # Nettoyer les événements utilisateur
            for user_id in list(self.user_events.keys()):
                events = self.user_events[user_id]
                while events and events[0].timestamp < cutoff_time:
                    events.popleft()
                
                if not events:
                    del self.user_events[user_id]
            
            # Nettoyer les événements des canaux
            for channel_id in list(self.channel_events.keys()):
                events = self.channel_events[channel_id]
                while events and events[0].timestamp < cutoff_time:
                    events.popleft()
                
                if not events:
                    del self.channel_events[channel_id]
            
            # Nettoyer les événements des serveurs
            for server_id in list(self.server_events.keys()):
                events = self.server_events[server_id]
                while events and events[0].timestamp < cutoff_time:
                    events.popleft()
                
                if not events:
                    del self.server_events[server_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupérer les statistiques du gestionnaire"""
        return {
            "active_user_connections": sum(len(conns) for conns in self.user_connections.values()),
            "active_channel_connections": sum(len(conns) for conns in self.channel_connections.values()),
            "active_server_connections": sum(len(conns) for conns in self.server_connections.values()),
            "total_user_events": sum(len(events) for events in self.user_events.values()),
            "total_channel_events": sum(len(events) for events in self.channel_events.values()),
            "total_server_events": sum(len(events) for events in self.server_events.values()),
        }

# Instance globale du gestionnaire
long_polling_manager = LongPollingManager()


# Fonctions utilitaires pour émettre des événements (similaires à SSE)

async def emit_message_created_lp(message_data: dict):
    """Émettre un événement de création de message via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.MESSAGE_CREATED,
        data=message_data,
        timestamp=datetime.now(timezone.utc),
        channel_id=message_data.get("channel_id"),
        server_id=message_data.get("server_id")
    )
    
    await long_polling_manager.add_event(event)

async def emit_message_updated_lp(message_data: dict):
    """Émettre un événement de mise à jour de message via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.MESSAGE_UPDATED,
        data=message_data,
        timestamp=datetime.now(timezone.utc),
        channel_id=message_data.get("channel_id"),
        server_id=message_data.get("server_id")
    )
    
    await long_polling_manager.add_event(event)

async def emit_message_deleted_lp(channel_id: str, message_id: str, server_id: Optional[str] = None):
    """Émettre un événement de suppression de message via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.MESSAGE_DELETED,
        data={"message_id": message_id, "channel_id": channel_id},
        timestamp=datetime.now(timezone.utc),
        channel_id=channel_id,
        server_id=server_id
    )
    
    await long_polling_manager.add_event(event)

async def emit_user_status_changed_lp(user_id: str, status_data: dict):
    """Émettre un événement de changement de statut utilisateur via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.USER_STATUS_CHANGED,
        data={"user_id": user_id, "status": status_data},
        timestamp=datetime.now(timezone.utc),
        user_id=user_id
    )
    
    await long_polling_manager.add_event(event)

async def emit_typing_indicator_lp(channel_id: str, user_id: str, is_typing: bool, server_id: Optional[str] = None):
    """Émettre un indicateur de frappe via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.TYPING_INDICATOR,
        data={
            "channel_id": channel_id,
            "user_id": user_id,
            "is_typing": is_typing
        },
        timestamp=datetime.now(timezone.utc),
        channel_id=channel_id,
        server_id=server_id
    )
    
    await long_polling_manager.add_event(event)

async def emit_server_member_joined_lp(server_id: str, user_id: str):
    """Émettre un événement de membre rejoignant un serveur via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.SERVER_MEMBER_JOINED,
        data={"server_id": server_id, "user_id": user_id},
        timestamp=datetime.now(timezone.utc),
        server_id=server_id
    )
    
    await long_polling_manager.add_event(event)

async def emit_server_member_left_lp(server_id: str, user_id: str):
    """Émettre un événement de membre quittant un serveur via long polling"""
    from nanoid import generate
    
    event = Event(
        id=generate(),
        type=EventType.SERVER_MEMBER_LEFT,
        data={"server_id": server_id, "user_id": user_id},
        timestamp=datetime.now(timezone.utc),
        server_id=server_id
    )
    
    await long_polling_manager.add_event(event)