"""
Configuration et données par défaut au démarrage
"""

from datetime import datetime, timezone
from ..core.database import Database
from ..core.config import settings

async def setup_default_data(db: Database):
    """Configurer les données par défaut lors du démarrage"""
    
    # Créer les index
    await db.initialize_indexes()
    
    # Vérifier si c'est la première installation
    admin_user = await db.get_user_by_username("admin")
    
    if admin_user is None:
        # Créer l'utilisateur administrateur par défaut
        from ..core.auth import auth_manager
        from nanoid import generate
        
        admin_data = {
            "_id": generate(),
            "username": "admin",
            "discriminator": "0001",
            "display_name": "Administrator",
            "email": settings.ADMIN_EMAIL,
            "password_hash": auth_manager.get_password_hash("admin123"),  # Mot de passe par défaut à changer
            "privileged": True,
            "badges": ["developer", "founder"],
            "flags": [],
            "created_at": datetime.now(timezone.utc),
            "status": {
                "text": "Setting up the server",
                "presence": "online"
            },
            "relationships": [],
            "federation": {
                "is_remote": False,
                "domain": settings.INSTANCE_DOMAIN
            }
        }
        
        user_id = await db.create_user(admin_data)
        print(f"✅ Utilisateur admin créé avec ID: {user_id}")
        print(f"⚠️  Mot de passe par défaut: admin123 (à changer immédiatement)")
    
    # Créer un canal général par défaut s'il n'existe pas
    general_channel = await db.channels.find_one({"name": "general", "server_id": None})
    
    if general_channel is None:
        from nanoid import generate
        
        channel_data = {
            "_id": generate(),
            "channel_type": "text",
            "name": "general",
            "description": "Canal général de l'instance",
            "server_id": None,
            "recipients": [],
            "nsfw": False,
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await db.channels.insert_one(channel_data)
        print(f"✅ Canal général créé avec ID: {result.inserted_id}")
    
    # Enregistrer cette instance dans la base de fédération
    local_instance = await db.get_federation_instance(settings.INSTANCE_DOMAIN)
    
    if local_instance is None:
        instance_data = {
            "_id": generate(),
            "domain": settings.INSTANCE_DOMAIN,
            "name": settings.INSTANCE_NAME,
            "description": settings.INSTANCE_DESCRIPTION,
            "software": {
                "name": "revolt-federated",
                "version": "1.0.0"
            },
            "protocols": ["activitypub"],
            "is_local": True,
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.register_federation_instance(instance_data)
        print(f"✅ Instance locale enregistrée: {settings.INSTANCE_DOMAIN}")
    
    print("🎉 Configuration initiale terminée")