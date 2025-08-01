"""
Endpoints ActivityPub pour la fédération
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse

from ...core.auth import get_current_user_optional
from ...core.database import Database
from ...core.federation import FederationManager
from ...core.config import settings
from ..dependencies import get_db

router = APIRouter()

async def get_federation_manager() -> FederationManager:
    """Dépendance pour récupérer le gestionnaire de fédération"""
    from ....server import app
    return app.state.federation

@router.get("/users/{username}")
async def get_user_actor(
    username: str,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Récupérer l'acteur ActivityPub d'un utilisateur local"""
    
    user = await db.get_user_by_username(username)
    if not user or "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # Vérifier que l'utilisateur est local
    if user.get("federation", {}).get("is_remote", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non local"
        )
    
    # Créer l'acteur ActivityPub
    actor = await federation.create_actor(user)
    
    return JSONResponse(
        content=actor,
        headers={
            "Content-Type": "application/activity+json; charset=utf-8"
        }
    )

@router.get("/servers/{server_id}")
async def get_server_actor(
    server_id: str,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Récupérer l'acteur ActivityPub d'un serveur local (Group)"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que le serveur est local et découvrable
    if (server.get("federation", {}).get("is_remote", False) or 
        not server.get("discoverable", True)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur non accessible"
        )
    
    # Créer l'acteur ActivityPub pour le serveur
    actor = await federation.create_group_actor(server)
    
    return JSONResponse(
        content=actor,
        headers={
            "Content-Type": "application/activity+json; charset=utf-8"
        }
    )

@router.get("/messages/{message_id}")
async def get_message_note(
    message_id: str,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Récupérer une Note ActivityPub pour un message"""
    
    message = await db.messages.find_one({"_id": message_id})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable"
        )
    
    # Vérifier que le message est local
    if message.get("federation", {}).get("is_remote", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message non local"
        )
    
    # Vérifier que le canal/serveur est public
    channel = await db.get_channel_by_id(message["channel_id"])
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    if channel["server_id"]:
        server = await db.get_server_by_id(channel["server_id"])
        if not server or not server.get("discoverable", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message non public"
            )
    
    # Récupérer l'auteur
    author = await db.get_user_by_id(message["author_id"])
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auteur introuvable"
        )
    
    # Créer la Note ActivityPub
    note = await federation.create_note_activity(message, author["username"])
    
    return JSONResponse(
        content=note,
        headers={
            "Content-Type": "application/activity+json; charset=utf-8"
        }
    )

@router.post("/users/{username}/inbox")
async def user_inbox(
    username: str,
    request: Request,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Boîte de réception ActivityPub d'un utilisateur"""
    
    # Vérifier que l'utilisateur existe
    user = await db.get_user_by_username(username)
    if not user or "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # Récupérer l'activité
    try:
        activity = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activité invalide"
        )
    
    # TODO: Vérifier la signature HTTP de l'activité
    
    # Traiter l'activité
    success = await federation.process_inbox_activity(activity, db)
    
    if success:
        return JSONResponse(
            content={"message": "Activité traitée"},
            status_code=202
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de traiter l'activité"
        )

@router.post("/servers/{server_id}/inbox")
async def server_inbox(
    server_id: str,
    request: Request,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Boîte de réception ActivityPub d'un serveur"""
    
    # Vérifier que le serveur existe
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Récupérer l'activité
    try:
        activity = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activité invalide"
        )
    
    # TODO: Vérifier la signature HTTP de l'activité
    
    # Traiter l'activité
    success = await federation.process_inbox_activity(activity, db)
    
    if success:
        return JSONResponse(
            content={"message": "Activité traitée"},
            status_code=202
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de traiter l'activité"
        )

@router.post("/inbox")
async def shared_inbox(
    request: Request,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Boîte de réception partagée de l'instance"""
    
    # Récupérer l'activité
    try:
        activity = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activité invalide"
        )
    
    # TODO: Vérifier la signature HTTP de l'activité
    
    # Stocker l'activité pour traitement
    await db.store_activitypub_activity(activity)
    
    # Traiter l'activité
    success = await federation.process_inbox_activity(activity, db)
    
    if success:
        return JSONResponse(
            content={"message": "Activité traitée"},
            status_code=202
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de traiter l'activité"
        )

@router.get("/users/{username}/outbox")
async def user_outbox(
    username: str,
    db: Database = Depends(get_db)
):
    """Boîte d'envoi ActivityPub d'un utilisateur"""
    
    user = await db.get_user_by_username(username)
    if not user or "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # Récupérer les activités publiques de l'utilisateur
    # TODO: Implémenter la récupération des activités de l'utilisateur
    
    outbox = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "OrderedCollection",
        "id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{username}/outbox",
        "totalItems": 0,
        "orderedItems": []
    }
    
    return JSONResponse(
        content=outbox,
        headers={
            "Content-Type": "application/activity+json; charset=utf-8"
        }
    )

@router.get("/users/{username}/followers")
async def user_followers(
    username: str,
    db: Database = Depends(get_db)
):
    """Liste des abonnés ActivityPub d'un utilisateur"""
    
    user = await db.get_user_by_username(username)
    if not user or "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # TODO: Implémenter la liste des abonnés
    
    followers = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "OrderedCollection",
        "id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{username}/followers",
        "totalItems": 0,
        "orderedItems": []
    }
    
    return JSONResponse(
        content=followers,
        headers={
            "Content-Type": "application/activity+json; charset=utf-8"
        }
    )

@router.get("/users/{username}/following")
async def user_following(
    username: str,
    db: Database = Depends(get_db)
):
    """Liste des abonnements ActivityPub d'un utilisateur"""
    
    user = await db.get_user_by_username(username)
    if not user or "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # TODO: Implémenter la liste des abonnements
    
    following = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "OrderedCollection",
        "id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{username}/following",
        "totalItems": 0,
        "orderedItems": []
    }
    
    return JSONResponse(
        content=following,
        headers={
            "Content-Type": "application/activity+json; charset=utf-8"
        }
    )

@router.get("/instances")
async def get_known_instances(
    db: Database = Depends(get_db)
):
    """Récupérer la liste des instances fédérées connues"""
    
    instances = await db.federation_instances.find(
        {"is_local": {"$ne": True}},
        {"domain": 1, "name": 1, "software": 1, "status": 1}
    ).to_list(None)
    
    return {"instances": instances}

@router.post("/discover")
async def discover_instance(
    domain: str,
    db: Database = Depends(get_db),
    federation: FederationManager = Depends(get_federation_manager)
):
    """Découvrir une nouvelle instance fédérée"""
    
    # Vérifier si l'instance est déjà connue
    existing = await db.get_federation_instance(domain)
    if existing:
        return {"message": "Instance déjà connue", "instance": existing}
    
    # Découvrir l'instance
    instance_info = await federation.discover_instance(domain)
    
    if instance_info:
        await db.register_federation_instance(instance_info)
        return {"message": "Instance découverte", "instance": instance_info}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de découvrir cette instance"
        )