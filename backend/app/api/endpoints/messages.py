"""
Endpoints de gestion des messages avec support de fédération
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timezone
from nanoid import generate

from ...core.auth import get_current_user
from ...core.config import settings
from ...models.message import MessageCreate, MessageUpdate, MessageResponse, MessageType, MessageSearchQuery
from ...sse.events import emit_message_created, emit_message_updated, emit_message_deleted
from ...utils.validation import clean_content, extract_mentions

router = APIRouter()

async def get_db():
    """Dépendance pour récupérer la base de données"""
    from ...server import app
    return app.state.db

@router.post("/{channel_id}", response_model=MessageResponse)
async def create_message(
    channel_id: str,
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Créer un nouveau message dans un canal"""
    
    # Vérifier que le canal existe et que l'utilisateur y a accès
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Vérifier les permissions d'accès au canal
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
    
    message_id = generate()
    
    # Nettoyer et traiter le contenu
    cleaned_content = None
    if message_data.content:
        cleaned_content = clean_content(message_data.content)
    
    # Extraire les mentions
    mentions = []
    if cleaned_content:
        mentions = extract_mentions(cleaned_content)
    
    # Traiter les pièces jointes
    attachments = []
    for attachment_id in message_data.attachments:
        # TODO: Récupérer les informations du fichier depuis la base de données
        # Pour l'instant, on suppose que les fichiers sont déjà uploadés
        attachment = {
            "id": attachment_id,
            "filename": f"file_{attachment_id}",
            "size": 0,
            "content_type": "application/octet-stream",
            "url": f"https://{settings.INSTANCE_DOMAIN}/uploads/{attachment_id}"
        }
        attachments.append(attachment)
    
    # Créer les données de fédération pour le message
    federation_data = {
        "activity_id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/activities/create-{message_id}",
        "note_id": f"https://{settings.INSTANCE_DOMAIN}/api/activitypub/messages/{message_id}",
        "origin_domain": settings.INSTANCE_DOMAIN,
        "is_remote": False
    }
    
    new_message = {
        "_id": message_id,
        "channel_id": channel_id,
        "author_id": current_user["_id"],
        "content": cleaned_content,
        "message_type": MessageType.TEXT,
        "attachments": attachments,
        "embeds": [],
        "mentions": mentions,
        "reactions": [],
        "created_at": datetime.now(timezone.utc),
        "reply_to": message_data.reply_to,
        "federation": federation_data
    }
    
    await db.create_message(new_message)
    
    # Mettre à jour le dernier message du canal
    await db.channels.update_one(
        {"_id": channel_id},
        {
            "$set": {
                "last_message_id": message_id,
                "last_message_at": new_message["created_at"]
            }
        }
    )
    
    # Émettre l'événement SSE
    await emit_message_created(new_message)
    
    # TODO: Si la fédération est activée et que le serveur/canal est fédéré,
    # créer et envoyer l'activité ActivityPub
    
    return MessageResponse(
        id=message_id,
        channel_id=new_message["channel_id"],
        author_id=new_message["author_id"],
        content=new_message["content"],
        message_type=new_message["message_type"],
        attachments=new_message["attachments"],
        embeds=new_message["embeds"],
        mentions=new_message["mentions"],
        reactions=new_message["reactions"],
        created_at=new_message["created_at"],
        reply_to=new_message["reply_to"],
        federation=new_message["federation"]
    )

@router.get("/{channel_id}")
async def get_messages(
    channel_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
    limit: int = Query(default=50, le=100, ge=1),
    before: Optional[str] = Query(default=None)
):
    """Récupérer les messages d'un canal"""
    
    # Vérifier que le canal existe et que l'utilisateur y a accès
    channel = await db.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Vérifier les permissions d'accès
    has_access = False
    
    if channel["server_id"]:
        server = await db.get_server_by_id(channel["server_id"])
        if server and current_user["_id"] in server.get("members", []):
            has_access = True
    else:
        if current_user["_id"] in channel.get("recipients", []):
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à ce canal"
        )
    
    # Récupérer les messages
    messages = await db.get_messages_by_channel(channel_id, limit, before)
    
    message_responses = []
    for message in messages:
        message_responses.append(MessageResponse(
            id=message["_id"],
            channel_id=message["channel_id"],
            author_id=message["author_id"],
            content=message.get("content"),
            message_type=message.get("message_type", MessageType.TEXT),
            attachments=message.get("attachments", []),
            embeds=message.get("embeds", []),
            mentions=message.get("mentions", []),
            reactions=message.get("reactions", []),
            created_at=message["created_at"],
            updated_at=message.get("updated_at"),
            edited_at=message.get("edited_at"),
            reply_to=message.get("reply_to"),
            federation=message.get("federation")
        ))
    
    return message_responses

@router.get("/message/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Récupérer un message spécifique"""
    
    message = await db.messages.find_one({"_id": message_id})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable"
        )
    
    # Vérifier l'accès au canal
    channel = await db.get_channel_by_id(message["channel_id"])
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # Vérifier les permissions
    has_access = False
    
    if channel["server_id"]:
        server = await db.get_server_by_id(channel["server_id"])
        if server and current_user["_id"] in server.get("members", []):
            has_access = True
    else:
        if current_user["_id"] in channel.get("recipients", []):
            has_access = True
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à ce message"
        )
    
    return MessageResponse(
        id=message["_id"],
        channel_id=message["channel_id"],
        author_id=message["author_id"],
        content=message.get("content"),
        message_type=message.get("message_type", MessageType.TEXT),
        attachments=message.get("attachments", []),
        embeds=message.get("embeds", []),
        mentions=message.get("mentions", []),
        reactions=message.get("reactions", []),
        created_at=message["created_at"],
        updated_at=message.get("updated_at"),
        edited_at=message.get("edited_at"),
        reply_to=message.get("reply_to"),
        federation=message.get("federation")
    )

@router.patch("/message/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    update_data: MessageUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Modifier un message"""
    
    message = await db.messages.find_one({"_id": message_id})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable"
        )
    
    # Vérifier que l'utilisateur est l'auteur du message
    if message["author_id"] != current_user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez modifier que vos propres messages"
        )
    
    # Nettoyer le nouveau contenu
    cleaned_content = clean_content(update_data.content) if update_data.content else None
    
    # Extraire les nouvelles mentions
    mentions = extract_mentions(cleaned_content) if cleaned_content else []
    
    update_fields = {
        "content": cleaned_content,
        "mentions": mentions,
        "updated_at": datetime.now(timezone.utc),
        "edited_at": datetime.now(timezone.utc)
    }
    
    await db.messages.update_one(
        {"_id": message_id},
        {"$set": update_fields}
    )
    
    # Récupérer le message mis à jour
    updated_message = await db.messages.find_one({"_id": message_id})
    
    # Émettre l'événement SSE
    await emit_message_updated(updated_message)
    
    return MessageResponse(
        id=updated_message["_id"],
        channel_id=updated_message["channel_id"],
        author_id=updated_message["author_id"],
        content=updated_message.get("content"),
        message_type=updated_message.get("message_type", MessageType.TEXT),
        attachments=updated_message.get("attachments", []),
        embeds=updated_message.get("embeds", []),
        mentions=updated_message.get("mentions", []),
        reactions=updated_message.get("reactions", []),
        created_at=updated_message["created_at"],
        updated_at=updated_message.get("updated_at"),
        edited_at=updated_message.get("edited_at"),
        reply_to=updated_message.get("reply_to"),
        federation=updated_message.get("federation")
    )

@router.delete("/message/{message_id}")
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Supprimer un message"""
    
    message = await db.messages.find_one({"_id": message_id})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable"
        )
    
    # Vérifier que l'utilisateur est l'auteur du message ou modérateur
    can_delete = False
    
    if message["author_id"] == current_user["_id"]:
        can_delete = True
    else:
        # Vérifier si l'utilisateur est modérateur du serveur
        channel = await db.get_channel_by_id(message["channel_id"])
        if channel and channel["server_id"]:
            server = await db.get_server_by_id(channel["server_id"])
            if server and server["owner_id"] == current_user["_id"]:
                can_delete = True
    
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas supprimer ce message"
        )
    
    # Supprimer le message
    await db.messages.delete_one({"_id": message_id})
    
    # Émettre l'événement SSE
    await emit_message_deleted(message["channel_id"], message_id)
    
    return {"message": "Message supprimé avec succès"}

@router.post("/message/{message_id}/react")
async def add_reaction(
    message_id: str,
    emoji: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Ajouter une réaction à un message"""
    
    message = await db.messages.find_one({"_id": message_id})
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable"
        )
    
    # Vérifier l'accès au canal
    channel = await db.get_channel_by_id(message["channel_id"])
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal introuvable"
        )
    
    # TODO: Vérifier les permissions d'accès
    
    # Ajouter la réaction
    await db.messages.update_one(
        {"_id": message_id, "reactions.emoji_id": {"$ne": emoji}},
        {"$push": {"reactions": {"emoji_id": emoji, "user_ids": [current_user["_id"]]}}}
    )
    
    # Si la réaction existe déjà, ajouter l'utilisateur
    await db.messages.update_one(
        {"_id": message_id, "reactions.emoji_id": emoji},
        {"$addToSet": {"reactions.$.user_ids": current_user["_id"]}}
    )
    
    return {"message": "Réaction ajoutée"}

@router.delete("/message/{message_id}/react")
async def remove_reaction(
    message_id: str,
    emoji: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Supprimer une réaction d'un message"""
    
    # Supprimer l'utilisateur de la réaction
    await db.messages.update_one(
        {"_id": message_id, "reactions.emoji_id": emoji},
        {"$pull": {"reactions.$.user_ids": current_user["_id"]}}
    )
    
    # Supprimer les réactions vides
    await db.messages.update_one(
        {"_id": message_id},
        {"$pull": {"reactions": {"user_ids": {"$size": 0}}}}
    )
    
    return {"message": "Réaction supprimée"}

@router.post("/search")
async def search_messages(
    search_query: MessageSearchQuery,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Rechercher des messages"""
    
    # Construire la requête MongoDB
    query = {"$text": {"$search": search_query.query}}
    
    if search_query.channel_id:
        # Vérifier l'accès au canal
        channel = await db.get_channel_by_id(search_query.channel_id)
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Canal introuvable"
            )
        
        # TODO: Vérifier les permissions d'accès
        query["channel_id"] = search_query.channel_id
    
    if search_query.author_id:
        query["author_id"] = search_query.author_id
    
    if search_query.before:
        query["created_at"] = {"$lt": search_query.before}
    
    if search_query.after:
        if "created_at" in query:
            query["created_at"]["$gt"] = search_query.after
        else:
            query["created_at"] = {"$gt": search_query.after}
    
    # Exécuter la recherche
    messages = await db.messages.find(query).limit(search_query.limit).to_list(None)
    
    # TODO: Filtrer les messages selon les permissions d'accès de l'utilisateur
    
    message_responses = []
    for message in messages:
        message_responses.append(MessageResponse(
            id=message["_id"],
            channel_id=message["channel_id"],
            author_id=message["author_id"],
            content=message.get("content"),
            message_type=message.get("message_type", MessageType.TEXT),
            attachments=message.get("attachments", []),
            embeds=message.get("embeds", []),
            mentions=message.get("mentions", []),
            reactions=message.get("reactions", []),
            created_at=message["created_at"],
            updated_at=message.get("updated_at"),
            edited_at=message.get("edited_at"),
            reply_to=message.get("reply_to"),
            federation=message.get("federation")
        ))
    
    return {
        "messages": message_responses,
        "total": len(message_responses)
    }