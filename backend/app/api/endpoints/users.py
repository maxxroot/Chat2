"""
Endpoints de gestion des utilisateurs
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone

from ...core.auth import get_current_user
from ...models.user import UserResponse, UserUpdate
from ...utils.validation import validate_display_name

router = APIRouter()

async def get_db():
    """Dépendance pour récupérer la base de données"""
    from ...server import app
    return app.state.db

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db = Depends(get_db)):
    """Récupérer un utilisateur par son ID"""
    
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # Ne pas retourner les utilisateurs supprimés
    if "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    return UserResponse(
        id=user["_id"],
        username=user["username"],
        discriminator=user["discriminator"],
        display_name=user.get("display_name"),
        avatar=user.get("avatar"),
        banner=user.get("banner"),
        badges=user.get("badges", []),
        flags=user.get("flags", []),
        privileged=user.get("privileged", False),
        created_at=user["created_at"],
        last_active=user.get("last_active"),
        federation=user.get("federation"),
        online=False  # TODO: Vérifier le statut en ligne
    )

@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Mettre à jour les informations de l'utilisateur actuel"""
    
    update_fields = {}
    
    if update_data.display_name is not None:
        if update_data.display_name and not validate_display_name(update_data.display_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom d'affichage invalide"
            )
        update_fields["display_name"] = update_data.display_name
    
    if update_data.avatar is not None:
        update_fields["avatar"] = update_data.avatar
    
    if update_data.banner is not None:
        update_fields["banner"] = update_data.banner
    
    if update_data.status is not None:
        update_fields["status"] = update_data.status.dict()
    
    if update_data.profile is not None:
        update_fields["profile"] = update_data.profile.dict()
    
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": update_fields}
        )
    
    # Récupérer l'utilisateur mis à jour
    updated_user = await db.get_user_by_id(current_user["_id"])
    
    return UserResponse(
        id=updated_user["_id"],
        username=updated_user["username"],
        discriminator=updated_user["discriminator"],
        display_name=updated_user.get("display_name"),
        avatar=updated_user.get("avatar"),
        banner=updated_user.get("banner"),
        badges=updated_user.get("badges", []),
        flags=updated_user.get("flags", []),
        privileged=updated_user.get("privileged", False),
        created_at=updated_user["created_at"],
        last_active=updated_user.get("last_active"),
        federation=updated_user.get("federation"),
        online=True
    )

@router.get("/{username}/profile")
async def get_user_profile(username: str, db = Depends(get_db)):
    """Récupérer le profil public d'un utilisateur"""
    
    user = await db.get_user_by_username(username)
    if not user or "deleted" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    return {
        "id": user["_id"],
        "username": user["username"],
        "discriminator": user["discriminator"],
        "display_name": user.get("display_name"),
        "avatar": user.get("avatar"),
        "banner": user.get("banner"),
        "badges": user.get("badges", []),
        "status": user.get("status"),
        "profile": user.get("profile"),
        "created_at": user["created_at"],
        "federation": user.get("federation")
    }

@router.post("/{user_id}/friend")
async def send_friend_request(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Envoyer une demande d'ami"""
    
    if user_id == current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous ajouter en ami"
        )
    
    # Vérifier que l'utilisateur cible existe
    target_user = await db.get_user_by_id(user_id)
    if not target_user or "deleted" in target_user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable"
        )
    
    # Vérifier la relation actuelle
    current_relations = current_user.get("relationships", [])
    existing_relation = next((r for r in current_relations if r["user_id"] == user_id), None)
    
    if existing_relation:
        if existing_relation["status"] == "friend":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vous êtes déjà amis"
            )
        elif existing_relation["status"] == "outgoing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Demande d'ami déjà envoyée"
            )
        elif existing_relation["status"] == "blocked":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous avez bloqué cet utilisateur"
            )
    
    # Ajouter la relation sortante pour l'utilisateur actuel
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$pull": {"relationships": {"user_id": user_id}},
            "$push": {"relationships": {"user_id": user_id, "status": "outgoing"}}
        }
    )
    
    # Ajouter la relation entrante pour l'utilisateur cible
    await db.users.update_one(
        {"_id": user_id},
        {
            "$pull": {"relationships": {"user_id": current_user["_id"]}},
            "$push": {"relationships": {"user_id": current_user["_id"], "status": "incoming"}}
        }
    )
    
    # TODO: Envoyer un événement SSE à l'utilisateur cible
    
    return {"message": "Demande d'ami envoyée"}

@router.put("/{user_id}/friend")
async def accept_friend_request(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Accepter une demande d'ami"""
    
    # Vérifier qu'il y a bien une demande entrante
    current_relations = current_user.get("relationships", [])
    incoming_relation = next((r for r in current_relations if r["user_id"] == user_id and r["status"] == "incoming"), None)
    
    if not incoming_relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune demande d'ami de cet utilisateur"
        )
    
    # Mettre à jour les relations pour les deux utilisateurs
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$pull": {"relationships": {"user_id": user_id}},
            "$push": {"relationships": {"user_id": user_id, "status": "friend"}}
        }
    )
    
    await db.users.update_one(
        {"_id": user_id},
        {
            "$pull": {"relationships": {"user_id": current_user["_id"]}},
            "$push": {"relationships": {"user_id": current_user["_id"], "status": "friend"}}
        }
    )
    
    # TODO: Envoyer un événement SSE aux deux utilisateurs
    
    return {"message": "Demande d'ami acceptée"}

@router.delete("/{user_id}/friend")
async def remove_friend_or_reject(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Supprimer un ami ou rejeter une demande"""
    
    # Supprimer la relation des deux côtés
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$pull": {"relationships": {"user_id": user_id}}}
    )
    
    await db.users.update_one(
        {"_id": user_id},
        {"$pull": {"relationships": {"user_id": current_user["_id"]}}}
    )
    
    return {"message": "Relation supprimée"}

@router.put("/{user_id}/block")
async def block_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Bloquer un utilisateur"""
    
    if user_id == current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous bloquer"
        )
    
    # Supprimer toute relation existante et ajouter le blocage
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$pull": {"relationships": {"user_id": user_id}},
            "$push": {"relationships": {"user_id": user_id, "status": "blocked"}}
        }
    )
    
    # Supprimer la relation côté cible et marquer comme bloqué
    await db.users.update_one(
        {"_id": user_id},
        {
            "$pull": {"relationships": {"user_id": current_user["_id"]}},
            "$push": {"relationships": {"user_id": current_user["_id"], "status": "blocked_other"}}
        }
    )
    
    return {"message": "Utilisateur bloqué"}

@router.delete("/{user_id}/block")
async def unblock_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Débloquer un utilisateur"""
    
    # Supprimer le blocage des deux côtés
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$pull": {"relationships": {"user_id": user_id}}}
    )
    
    await db.users.update_one(
        {"_id": user_id},
        {"$pull": {"relationships": {"user_id": current_user["_id"]}}}
    )
    
    return {"message": "Utilisateur débloqué"}