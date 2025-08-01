"""
Endpoints de gestion des canaux
"""

from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from nanoid import generate

from ...core.auth import get_current_user
from ...core.database import Database
from ...models.channel import ChannelCreate, ChannelUpdate, ChannelResponse, ChannelType
from ...utils.validation import validate_channel_name
from ..dependencies import get_db

router = APIRouter()

@router.post("", response_model=ChannelResponse)
async def create_channel(
    channel_data: ChannelCreate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Créer un nouveau canal"""
    
    # Validation selon le type de canal
    if channel_data.channel_type in [ChannelType.TEXT, ChannelType.VOICE]:
        if not channel_data.name or not validate_channel_name(channel_data.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom de canal invalide"
            )
    
    channel_id = generate()
    
    new_channel = {
        "_id": channel_id,
        "channel_type": channel_data.channel_type,
        "name": channel_data.name,
        "description": channel_data.description,
        "server_id": None,  # Les canaux de serveur sont créés via l'API serveur
        "recipients": channel_data.recipients,
        "nsfw": channel_data.nsfw,
        "created_at": datetime.now(timezone.utc)
    }
    
    # Pour les canaux DM/Group, vérifier les destinataires
    if channel_data.channel_type in [ChannelType.DM, ChannelType.GROUP]:
        if not channel_data.recipients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Les destinataires sont requis pour ce type de canal"
            )
        
        # Ajouter l'utilisateur actuel aux destinataires s'il n'y est pas
        if current_user["_id"] not in channel_data.recipients:
            new_channel["recipients"].append(current_user["_id"])
        
        # Vérifier que tous les destinataires existent
        for recipient_id in new_channel["recipients"]:
            recipient = await db.get_user_by_id(recipient_id)
            if not recipient:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Utilisateur {recipient_id} introuvable"
                )
    
    await db.channels.insert_one(new_channel)
    
    return ChannelResponse(
        id=channel_id,
        channel_type=new_channel["channel_type"],
        name=new_channel["name"],
        description=new_channel["description"],
        server_id=new_channel["server_id"],
        recipients=new_channel["recipients"],
        nsfw=new_channel["nsfw"],
        created_at=new_channel["created_at"],
        message_count=0
    )

@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Récupérer un canal par son ID"""
    
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Vérifier les permissions d'accès
    has_access = False
    
    if channel["server_id"]:
        # Canal de serveur - vérifier l'adhésion au serveur
        server = await db.get_server_by_id(channel["server_id"])
        if server and current_user["_id"] in server.get("members", []):
            has_access = True
    else:
        # Canal DM/Group - vérifier que l'utilisateur est dans les destinataires
        if current_user["_id"] in channel.get("recipients", []):
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à ce canal"
        )
    
    # Compter les messages
    message_count = await db.messages.count_documents({"channel_id": channel_id})
    
    return ChannelResponse(
        id=channel["_id"],
        channel_type=channel["channel_type"],
        name=channel.get("name"),
        description=channel.get("description"),
        server_id=channel.get("server_id"),
        recipients=channel.get("recipients", []),
        icon=channel.get("icon"),
        nsfw=channel.get("nsfw", False),
        last_message_id=channel.get("last_message_id"),
        last_message_at=channel.get("last_message_at"),
        created_at=channel["created_at"],
        updated_at=channel.get("updated_at"),
        message_count=message_count
    )

@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    update_data: ChannelUpdate,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Mettre à jour un canal"""
    
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Vérifier les permissions de modification
    can_edit = False
    
    if channel["server_id"]:
        # Canal de serveur - vérifier que l'utilisateur est propriétaire du serveur
        server = await db.get_server_by_id(channel["server_id"])
        if server and server["owner_id"] == current_user["_id"]:
            can_edit = True
    else:
        # Canal DM/Group - tous les participants peuvent modifier (pour les groupes)
        if channel["channel_type"] == ChannelType.GROUP and current_user["_id"] in channel.get("recipients", []):
            can_edit = True
    
    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas le droit de modifier ce canal"
        )
    
    update_fields = {}
    
    if update_data.name is not None:
        if channel["channel_type"] in [ChannelType.TEXT, ChannelType.VOICE]:
            if not validate_channel_name(update_data.name):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nom de canal invalide"
                )
        update_fields["name"] = update_data.name
    
    if update_data.description is not None:
        update_fields["description"] = update_data.description
    
    if update_data.icon is not None:
        update_fields["icon"] = update_data.icon
    
    if update_data.nsfw is not None:
        update_fields["nsfw"] = update_data.nsfw
    
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        
        await db.channels.update_one(
            {"_id": channel_id},
            {"$set": update_fields}
        )
    
    # Récupérer le canal mis à jour
    updated_channel = await db.get_channel_by_id(channel_id)
    
    # Compter les messages
    message_count = await db.messages.count_documents({"channel_id": channel_id})
    
    return ChannelResponse(
        id=updated_channel["_id"],
        channel_type=updated_channel["channel_type"],
        name=updated_channel.get("name"),
        description=updated_channel.get("description"),
        server_id=updated_channel.get("server_id"),
        recipients=updated_channel.get("recipients", []),
        icon=updated_channel.get("icon"),
        nsfw=updated_channel.get("nsfw", False),
        last_message_id=updated_channel.get("last_message_id"),
        last_message_at=updated_channel.get("last_message_at"),
        created_at=updated_channel["created_at"],
        updated_at=updated_channel.get("updated_at"),
        message_count=message_count
    )

@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Supprimer un canal"""
    
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Vérifier les permissions de suppression
    can_delete = False
    
    if channel["server_id"]:
        # Canal de serveur - vérifier que l'utilisateur est propriétaire du serveur
        server = await db.get_server_by_id(channel["server_id"])
        if server and server["owner_id"] == current_user["_id"]:
            can_delete = True
            
            # Empêcher la suppression du dernier canal
            channels = await db.get_channels_by_server(channel["server_id"])
            if len(channels) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Impossible de supprimer le dernier canal du serveur"
                )
    else:
        # Canal DM/Group - tous les participants peuvent supprimer (quitter)
        if current_user["_id"] in channel.get("recipients", []):
            can_delete = True
    
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas le droit de supprimer ce canal"
        )
    
    # Supprimer le canal et tous ses messages
    await db.channels.delete_one({"_id": channel_id})
    await db.messages.delete_many({"channel_id": channel_id})
    
    return {"message": "Canal supprimé avec succès"}

@router.get("/")
async def get_user_channels(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Récupérer tous les canaux accessibles à l'utilisateur"""
    
    # Canaux DM/Group où l'utilisateur est destinataire
    dm_channels = await db.channels.find({
        "server_id": None,
        "recipients": current_user["_id"]
    }).to_list(None)
    
    # Canaux de serveur où l'utilisateur est membre
    user_servers = await db.get_servers_by_user(current_user["_id"])
    server_channels = []
    
    for server in user_servers:
        channels = await db.get_channels_by_server(server["_id"])
        server_channels.extend(channels)
    
    all_channels = dm_channels + server_channels
    
    channel_responses = []
    for channel in all_channels:
        # Compter les messages
        message_count = await db.messages.count_documents({"channel_id": channel["_id"]})
        
        channel_responses.append(ChannelResponse(
            id=channel["_id"],
            channel_type=channel["channel_type"],
            name=channel.get("name"),
            description=channel.get("description"),
            server_id=channel.get("server_id"),
            recipients=channel.get("recipients", []),
            icon=channel.get("icon"),
            nsfw=channel.get("nsfw", False),
            last_message_id=channel.get("last_message_id"),
            last_message_at=channel.get("last_message_at"),
            created_at=channel["created_at"],
            updated_at=channel.get("updated_at"),
            message_count=message_count
        ))
    
    return channel_responses

@router.post("/{channel_id}/typing")
async def start_typing(
    channel_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Indiquer que l'utilisateur tape dans un canal"""
    
    # Vérifier l'accès au canal
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # TODO: Vérifier les permissions d'accès
    
    # Émettre l'indicateur de frappe
    from ...sse.events import emit_typing_indicator
    await emit_typing_indicator(channel_id, current_user["_id"], True)
    
    return {"message": "Indicateur de frappe envoyé"}