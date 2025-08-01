"""
Endpoints Long Polling pour les événements temps réel
Alternative au SSE (Server-Sent Events)
"""

import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timezone

from ..core.auth import get_current_user
from ..core.database import Database
from ..api.dependencies import get_db
from .manager import long_polling_manager, Event

router = APIRouter()

@router.get("/poll")
async def poll_events(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    last_event_id: Optional[str] = Query(None, description="Dernier ID d'événement reçu"),
    timeout: float = Query(30.0, ge=1.0, le=60.0, description="Timeout en secondes"),
    channels: Optional[str] = Query(None, description="IDs des canaux séparés par des virgules"),
    servers: Optional[str] = Query(None, description="IDs des serveurs séparés par des virgules")
):
    """
    Endpoint de long polling pour récupérer les événements temps réel
    
    Le client fait une requête qui reste ouverte jusqu'à ce qu'il y ait 
    de nouveaux événements ou que le timeout soit atteint.
    """
    
    # Parser les listes de canaux et serveurs
    channel_list = None
    if channels:
        channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    
    server_list = None
    if servers:
        server_list = [s.strip() for s in servers.split(",") if s.strip()]
    
    # Vérifier les permissions d'accès aux canaux
    if channel_list:
        for channel_id in channel_list:
            channel = await db.get_channel_by_id(channel_id)
            if not channel:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Canal {channel_id} introuvable"
                )
            
            # Vérifier l'accès au canal
            has_access = False
            
            if channel["server_id"]:
                # Canal de serveur - vérifier l'adhésion
                server = await db.get_server_by_id(channel["server_id"])
                if server and current_user["_id"] in server.get("members", []):
                    has_access = True
            else:
                # Canal DM/Group - vérifier les destinataires
                if current_user["_id"] in channel.get("recipients", []):
                    has_access = True
            
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Accès refusé au canal {channel_id}"
                )
    
    # Vérifier les permissions d'accès aux serveurs
    if server_list:
        for server_id in server_list:
            server = await db.get_server_by_id(server_id)
            if not server:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Serveur {server_id} introuvable"
                )
            
            if current_user["_id"] not in server.get("members", []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Accès refusé au serveur {server_id}"
                )
    
    try:
        # Attendre les événements
        events = await long_polling_manager.wait_for_events(
            user_id=current_user["_id"],
            last_event_id=last_event_id,
            timeout=timeout,
            channels=channel_list,
            servers=server_list
        )
        
        # Convertir les événements en dictionnaires pour la réponse JSON
        events_data = []
        for event in events:
            events_data.append({
                "id": event.id,
                "type": event.type,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "channel_id": event.channel_id,
                "server_id": event.server_id
            })
        
        return {
            "events": events_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_more": len(events) > 0
        }
    
    except asyncio.CancelledError:
        # La requête a été annulée par le client
        return {
            "events": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_more": False,
            "cancelled": True
        }

@router.get("/poll/channel/{channel_id}")
async def poll_channel_events(
    channel_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    last_event_id: Optional[str] = Query(None, description="Dernier ID d'événement reçu"),
    timeout: float = Query(30.0, ge=1.0, le=60.0, description="Timeout en secondes")
):
    """Long polling spécifique à un canal"""
    
    # Vérifier l'accès au canal
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    has_access = False
    server_id = None
    
    if channel["server_id"]:
        server_id = channel["server_id"]
        server = await db.get_server_by_id(server_id)
        if server and current_user["_id"] in server.get("members", []):
            has_access = True
    else:
        if current_user["_id"] in channel.get("recipients", []):
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé au canal"
        )
    
    try:
        # Attendre les événements du canal
        events = await long_polling_manager.wait_for_events(
            user_id=current_user["_id"],
            last_event_id=last_event_id,
            timeout=timeout,
            channels=[channel_id],
            servers=[server_id] if server_id else None
        )
        
        # Convertir en réponse JSON
        events_data = []
        for event in events:
            events_data.append({
                "id": event.id,
                "type": event.type,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "channel_id": event.channel_id,
                "server_id": event.server_id
            })
        
        return {
            "events": events_data,
            "channel_id": channel_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_more": len(events) > 0
        }
    
    except asyncio.CancelledError:
        return {
            "events": [],
            "channel_id": channel_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_more": False,
            "cancelled": True
        }

@router.get("/poll/server/{server_id}")
async def poll_server_events(
    server_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    last_event_id: Optional[str] = Query(None, description="Dernier ID d'événement reçu"),
    timeout: float = Query(30.0, ge=1.0, le=60.0, description="Timeout en secondes")
):
    """Long polling spécifique à un serveur"""
    
    # Vérifier l'accès au serveur
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    if current_user["_id"] not in server.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé au serveur"
        )
    
    try:
        # Attendre les événements du serveur
        events = await long_polling_manager.wait_for_events(
            user_id=current_user["_id"],
            last_event_id=last_event_id,
            timeout=timeout,
            servers=[server_id]
        )
        
        # Convertir en réponse JSON
        events_data = []
        for event in events:
            events_data.append({
                "id": event.id,
                "type": event.type,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "channel_id": event.channel_id,
                "server_id": event.server_id
            })
        
        return {
            "events": events_data,
            "server_id": server_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_more": len(events) > 0
        }
    
    except asyncio.CancelledError:
        return {
            "events": [],
            "server_id": server_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "has_more": False,
            "cancelled": True
        }

@router.get("/stats")
async def get_polling_stats(
    current_user: dict = Depends(get_current_user)
):
    """Récupérer les statistiques du système de long polling (admin uniquement)"""
    
    if not current_user.get("privileged", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès administrateur requis"
        )
    
    stats = long_polling_manager.get_stats()
    
    return {
        "long_polling_stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/cleanup")
async def cleanup_old_events(
    current_user: dict = Depends(get_current_user),
    max_age_hours: int = Query(default=24, ge=1, le=168, description="Âge maximum en heures")
):
    """Nettoyer les anciens événements (admin uniquement)"""
    
    if not current_user.get("privileged", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès administrateur requis"
        )
    
    await long_polling_manager.cleanup_old_events(max_age_hours)
    
    return {
        "message": f"Événements plus anciens que {max_age_hours}h nettoyés",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }