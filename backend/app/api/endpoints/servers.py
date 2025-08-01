"""
Endpoints de gestion des serveurs
"""

from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone, timedelta
from nanoid import generate

from ...core.auth import get_current_user
from ...core.config import settings
from ...core.database import Database
from ...models.server import ServerCreate, ServerUpdate, ServerResponse, ServerInviteCreate, ServerInviteResponse
from ...models.channel import ChannelCreate, ChannelType
from ...sse.events import emit_server_member_joined, emit_server_member_left
from ...utils.validation import validate_server_name
from ..dependencies import get_db

router = APIRouter()

@router.post("", response_model=ServerResponse)
async def create_server(
    server_data: ServerCreate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Créer un nouveau serveur"""
    
    if not validate_server_name(server_data.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom de serveur invalide"
        )
    
    server_id = generate()
    
    # Créer les données de fédération pour le serveur
    federation_data = {
        "actor_id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/servers/{server_id}",
        "domain": settings.INSTANCE_DOMAIN,
        "inbox_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/servers/{server_id}/inbox",
        "outbox_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/servers/{server_id}/outbox",
        "following_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/servers/{server_id}/following",
        "followers_url": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/servers/{server_id}/followers",
        "is_remote": False
    }
    
    new_server = {
        "_id": server_id,
        "name": server_data.name,
        "description": server_data.description,
        "owner_id": current_user["_id"],
        "members": [current_user["_id"]],  # Le créateur est automatiquement membre
        "nsfw": server_data.nsfw,
        "discoverable": server_data.discoverable,
        "analytics": False,
        "flags": [],
        "created_at": datetime.now(timezone.utc),
        "federation": federation_data
    }
    
    await db.servers.insert_one(new_server)
    
    # Créer un canal général par défaut
    general_channel = {
        "_id": generate(),
        "channel_type": "text",
        "name": "general",
        "description": "Canal général du serveur",
        "server_id": server_id,
        "recipients": [],
        "nsfw": False,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.channels.insert_one(general_channel)
    
    # Créer l'adhésion du serveur pour le créateur
    member_data = {
        "_id": f"{server_id}:{current_user['_id']}",
        "server_id": server_id,
        "user_id": current_user["_id"],
        "nickname": None,
        "avatar": None,
        "roles": [],
        "joined_at": datetime.now(timezone.utc)
    }
    
    await db.db.server_members.insert_one(member_data)
    
    return ServerResponse(
        id=server_id,
        name=new_server["name"],
        description=new_server["description"],
        owner_id=new_server["owner_id"],
        nsfw=new_server["nsfw"],
        discoverable=new_server["discoverable"],
        analytics=new_server["analytics"],
        flags=new_server["flags"],
        created_at=new_server["created_at"],
        federation=new_server["federation"],
        member_count=1,
        channel_count=1
    )

@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Récupérer un serveur par son ID"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que l'utilisateur est membre du serveur
    if current_user["_id"] not in server.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à ce serveur"
        )
    
    # Compter les membres et canaux
    member_count = len(server.get("members", []))
    channels = await db.get_channels_by_server(server_id)
    channel_count = len(channels)
    
    return ServerResponse(
        id=server["_id"],
        name=server["name"],
        description=server.get("description"),
        owner_id=server["owner_id"],
        icon=server.get("icon"),
        banner=server.get("banner"),
        nsfw=server.get("nsfw", False),
        discoverable=server.get("discoverable", True),
        analytics=server.get("analytics", False),
        system_messages=server.get("system_messages"),
        flags=server.get("flags", []),
        created_at=server["created_at"],
        updated_at=server.get("updated_at"),
        federation=server.get("federation"),
        member_count=member_count,
        channel_count=channel_count
    )

@router.patch("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: str,
    update_data: ServerUpdate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Mettre à jour un serveur"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que l'utilisateur est le propriétaire
    if server["owner_id"] != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le propriétaire peut modifier le serveur"
        )
    
    update_fields = {}
    
    if update_data.name is not None:
        if not validate_server_name(update_data.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom de serveur invalide"
            )
        update_fields["name"] = update_data.name
    
    if update_data.description is not None:
        update_fields["description"] = update_data.description
    
    if update_data.icon is not None:
        update_fields["icon"] = update_data.icon
    
    if update_data.banner is not None:
        update_fields["banner"] = update_data.banner
    
    if update_data.nsfw is not None:
        update_fields["nsfw"] = update_data.nsfw
    
    if update_data.discoverable is not None:
        update_fields["discoverable"] = update_data.discoverable
    
    if update_data.analytics is not None:
        update_fields["analytics"] = update_data.analytics
    
    if update_data.system_messages is not None:
        update_fields["system_messages"] = update_data.system_messages.dict()
    
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        
        await db.servers.update_one(
            {"_id": server_id},
            {"$set": update_fields}
        )
    
    # Récupérer le serveur mis à jour
    updated_server = await db.get_server_by_id(server_id)
    
    # Compter les membres et canaux
    member_count = len(updated_server.get("members", []))
    channels = await db.get_channels_by_server(server_id)
    channel_count = len(channels)
    
    return ServerResponse(
        id=updated_server["_id"],
        name=updated_server["name"],
        description=updated_server.get("description"),
        owner_id=updated_server["owner_id"],
        icon=updated_server.get("icon"),
        banner=updated_server.get("banner"),
        nsfw=updated_server.get("nsfw", False),
        discoverable=updated_server.get("discoverable", True),
        analytics=updated_server.get("analytics", False),
        system_messages=updated_server.get("system_messages"),
        flags=updated_server.get("flags", []),
        created_at=updated_server["created_at"],
        updated_at=updated_server.get("updated_at"),
        federation=updated_server.get("federation"),
        member_count=member_count,
        channel_count=channel_count
    )

@router.delete("/{server_id}")
async def delete_server(
    server_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Supprimer un serveur"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que l'utilisateur est le propriétaire
    if server["owner_id"] != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le propriétaire peut supprimer le serveur"
        )
    
    # Supprimer le serveur, ses canaux et ses messages
    await db.servers.delete_one({"_id": server_id})
    await db.channels.delete_many({"server_id": server_id})
    
    # Supprimer tous les messages des canaux du serveur
    channels = await db.get_channels_by_server(server_id)
    for channel in channels:
        await db.messages.delete_many({"channel_id": channel["_id"]})
    
    # Supprimer les adhésions
    await db.db.server_members.delete_many({"server_id": server_id})
    
    return {"message": "Serveur supprimé avec succès"}

@router.post("/{server_id}/join")
async def join_server(
    server_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Rejoindre un serveur public"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que le serveur est découvrable
    if not server.get("discoverable", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce serveur n'est pas public"
        )
    
    # Vérifier que l'utilisateur n'est pas déjà membre
    if current_user["_id"] in server.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vous êtes déjà membre de ce serveur"
        )
    
    # Ajouter l'utilisateur aux membres
    await db.servers.update_one(
        {"_id": server_id},
        {"$push": {"members": current_user["_id"]}}
    )
    
    # Créer l'adhésion
    member_data = {
        "_id": f"{server_id}:{current_user['_id']}",
        "server_id": server_id,
        "user_id": current_user["_id"],
        "nickname": None,
        "avatar": None,
        "roles": [],
        "joined_at": datetime.now(timezone.utc)
    }
    
    await db.db.server_members.insert_one(member_data)
    
    # Émettre un événement
    await emit_server_member_joined(server_id, current_user["_id"])
    
    return {"message": "Vous avez rejoint le serveur"}

@router.post("/{server_id}/leave")
async def leave_server(
    server_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Quitter un serveur"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que l'utilisateur est membre
    if current_user["_id"] not in server.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vous n'êtes pas membre de ce serveur"
        )
    
    # Le propriétaire ne peut pas quitter son serveur
    if server["owner_id"] == current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le propriétaire ne peut pas quitter le serveur"
        )
    
    # Supprimer l'utilisateur des membres
    await db.servers.update_one(
        {"_id": server_id},
        {"$pull": {"members": current_user["_id"]}}
    )
    
    # Supprimer l'adhésion
    await db.db.server_members.delete_one({
        "_id": f"{server_id}:{current_user['_id']}"
    })
    
    # Émettre un événement
    await emit_server_member_left(server_id, current_user["_id"])
    
    return {"message": "Vous avez quitté le serveur"}

@router.post("/{server_id}/invites", response_model=ServerInviteResponse)
async def create_invite(
    server_id: str,
    invite_data: ServerInviteCreate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Créer une invitation pour un serveur"""
    
    server = await db.get_server_by_id(server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Serveur introuvable"
        )
    
    # Vérifier que l'utilisateur est membre
    if current_user["_id"] not in server.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous devez être membre du serveur"
        )
    
    # Vérifier que le canal existe
    channel = await db.get_channel_by_id(invite_data.channel_id)
    if not channel or channel["server_id"] != server_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Générer un code d'invitation unique
    import secrets
    import string
    code = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    
    expires_at = None
    if invite_data.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=invite_data.expires_in)
    
    invite = {
        "_id": generate(),
        "server_id": server_id,
        "channel_id": invite_data.channel_id,
        "creator_id": current_user["_id"],
        "code": code,
        "uses": 0,
        "max_uses": invite_data.max_uses,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.db.server_invites.insert_one(invite)
    
    return ServerInviteResponse(
        code=code,
        server_id=server_id,
        channel_id=invite_data.channel_id,
        uses=0,
        max_uses=invite_data.max_uses,
        expires_at=expires_at,
        created_at=invite["created_at"]
    )

@router.get("/")
async def get_user_servers(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Récupérer tous les serveurs de l'utilisateur"""
    
    servers = await db.get_servers_by_user(current_user["_id"])
    
    server_responses = []
    for server in servers:
        # Compter les membres et canaux
        member_count = len(server.get("members", []))
        channels = await db.get_channels_by_server(server["_id"])
        channel_count = len(channels)
        
        server_responses.append(ServerResponse(
            id=server["_id"],
            name=server["name"],
            description=server.get("description"),
            owner_id=server["owner_id"],
            icon=server.get("icon"),
            banner=server.get("banner"),
            nsfw=server.get("nsfw", False),
            discoverable=server.get("discoverable", True),
            analytics=server.get("analytics", False),
            system_messages=server.get("system_messages"),
            flags=server.get("flags", []),
            created_at=server["created_at"],
            updated_at=server.get("updated_at"),
            federation=server.get("federation"),
            member_count=member_count,
            channel_count=channel_count
        ))
    
    return server_responses