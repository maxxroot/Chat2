"""
Endpoints d'authentification
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from datetime import datetime, timezone
from typing import Dict, Any
from nanoid import generate

from ...core.database import Database
from ...core.auth import auth_manager, get_current_user
from ...core.config import settings
from ...models.user import UserCreate, UserLogin, UserWithToken, UserResponse
from ...utils.validation import validate_username
from ..dependencies import get_db

router = APIRouter()

@router.post("/register", response_model=UserWithToken)
async def register(user_data: UserCreate, request: Request, db: Database = Depends(get_db)):
    """Créer un nouveau compte utilisateur"""
    
    # Valider le nom d'utilisateur
    if not validate_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom d'utilisateur invalide"
        )
    
    # Vérifier que l'utilisateur n'existe pas déjà
    existing_user = await db.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom d'utilisateur est déjà pris"
        )
    
    existing_email = await db.get_user_by_email(user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà utilisée"
        )
    
    # Créer l'utilisateur
    user_id = generate()
    discriminator = auth_manager.generate_discriminator()
    
    # Créer les données de fédération pour l'utilisateur local
    federation_data = {
        "actor_id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{user_data.username}",
        "domain": settings.INSTANCE_DOMAIN,
        "inbox_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{user_data.username}/inbox",
        "outbox_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{user_data.username}/outbox",
        "following_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{user_data.username}/following",
        "followers_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/users/{user_data.username}/followers",
        "is_remote": False
    }
    
    new_user = {
        "_id": user_id,
        "username": user_data.username,
        "discriminator": discriminator,
        "display_name": user_data.display_name or user_data.username,
        "email": user_data.email,
        "password_hash": auth_manager.get_password_hash(user_data.password),
        "badges": [],
        "flags": [],
        "privileged": False,
        "status": {
            "text": None,
            "presence": "online"
        },
        "relationships": [],
        "created_at": datetime.now(timezone.utc),
        "last_active": datetime.now(timezone.utc),
        "federation": federation_data
    }
    
    await db.create_user(new_user)
    
    # Créer une session
    user_agent = request.headers.get("user-agent")
    session = await auth_manager.create_session(db, user_id, user_agent)
    
    # Retourner l'utilisateur et le token
    user_response = UserResponse(
        id=user_id,
        username=new_user["username"],
        discriminator=new_user["discriminator"],
        display_name=new_user["display_name"],
        badges=new_user["badges"],
        flags=new_user["flags"],
        privileged=new_user["privileged"],
        created_at=new_user["created_at"],
        last_active=new_user["last_active"],
        federation=new_user["federation"],
        online=True
    )
    
    return UserWithToken(
        user=user_response,
        token=session["token"],
        expires_at=session["expires_at"]
    )

@router.post("/login", response_model=UserWithToken)
async def login(login_data: UserLogin, request: Request, db: Database = Depends(get_db)):
    """Se connecter avec username/email et mot de passe"""
    
    # Trouver l'utilisateur (par username ou email)
    user = None
    if "@" in login_data.login:
        user = await db.get_user_by_email(login_data.login)
    else:
        user = await db.get_user_by_username(login_data.login)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects"
        )
    
    # Vérifier le mot de passe
    if not auth_manager.verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects"
        )
    
    # Vérifier que l'utilisateur n'est pas banni
    if "banned" in user.get("flags", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte a été banni"
        )
    
    # Mettre à jour la dernière activité
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_active": datetime.now(timezone.utc)}}
    )
    
    # Créer une session
    user_agent = request.headers.get("user-agent")
    session = await auth_manager.create_session(db, user["_id"], user_agent)
    
    # Retourner l'utilisateur et le token
    user_response = UserResponse(
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
        online=True
    )
    
    return UserWithToken(
        user=user_response,
        token=session["token"],
        expires_at=session["expires_at"]
    )

@router.post("/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    """Se déconnecter (révoquer la session actuelle)"""
    
    # Récupérer l'ID de session depuis le token (à implémenter)
    # Pour l'instant, on révoque toutes les sessions
    revoked_count = await auth_manager.revoke_all_sessions(db, current_user["_id"])
    
    return {"message": f"{revoked_count} session(s) révoquée(s)"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Récupérer les informations de l'utilisateur actuel"""
    
    return UserResponse(
        id=current_user["_id"],
        username=current_user["username"],
        discriminator=current_user["discriminator"],
        display_name=current_user.get("display_name"),
        avatar=current_user.get("avatar"),
        banner=current_user.get("banner"),
        badges=current_user.get("badges", []),
        flags=current_user.get("flags", []),
        privileged=current_user.get("privileged", False),
        created_at=current_user["created_at"],
        last_active=current_user.get("last_active"),
        federation=current_user.get("federation"),
        online=True
    )

@router.delete("/me")
async def delete_account(current_user: Dict[str, Any] = Depends(get_current_user), db: Database = Depends(get_db)):
    """Supprimer son compte"""
    
    # Marquer l'utilisateur comme supprimé au lieu de le supprimer complètement
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "flags": list(set(current_user.get("flags", []) + ["deleted"])),
                "deleted_at": datetime.now(timezone.utc)
            },
            "$unset": {
                "email": 1,
                "password_hash": 1
            }
        }
    )
    
    # Révoquer toutes les sessions
    await auth_manager.revoke_all_sessions(db, current_user["_id"])
    
    return {"message": "Compte supprimé avec succès"}