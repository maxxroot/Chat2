"""
Revolt Backend - Serveur principal FastAPI avec fédération native
"""

import os
import asyncio
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.database import Database
from app.core.federation import FederationManager
from app.api.routes import api_router
from app.sse import sse_router
from app.longpolling import longpolling_router
from app.utils.startup import setup_default_data

# Gestionnaire de cycle de vie
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    # Startup
    print("🚀 Démarrage de Revolt Backend (Python + Fédération)")
    
    # Connexion à la base de données
    app.state.db_client = AsyncIOMotorClient(settings.MONGO_URL)
    app.state.db = Database(app.state.db_client)
    
    # Initialiser le gestionnaire de fédération
    app.state.federation = FederationManager(
        domain=settings.INSTANCE_DOMAIN,
        name=settings.INSTANCE_NAME,
        description=settings.INSTANCE_DESCRIPTION
    )
    
    # Configuration initiale de la base de données
    await setup_default_data(app.state.db)
    
    print(f"✅ Instance fédérée prête sur {settings.INSTANCE_DOMAIN}")
    
    yield
    
    # Shutdown
    print("🛑 Arrêt de Revolt Backend")
    app.state.db_client.close()

# Création de l'application FastAPI
app = FastAPI(
    title="Revolt Backend (Fédéré)",
    description="Backend Python pour Revolt avec fédération ActivityPub native",
    version="1.0.0",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes principales
app.include_router(api_router, prefix="/api")
app.include_router(sse_router, prefix="/events")

# Servir les fichiers statiques (pour les médias)
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def root():
    """Point d'entrée principal avec informations sur l'instance"""
    return {
        "name": settings.INSTANCE_NAME,
        "description": settings.INSTANCE_DESCRIPTION,
        "domain": settings.INSTANCE_DOMAIN,
        "federation_enabled": settings.FEDERATION_ENABLED,
        "version": "1.0.0",
        "protocol": "activitypub",
        "revolt_compatible": True
    }

@app.get("/.well-known/nodeinfo")
async def nodeinfo():
    """Endpoint NodeInfo pour la découverte de fédération"""
    return {
        "links": [
            {
                "rel": "http://nodeinfo.diaspora.software/ns/schema/2.0",
                "href": f"https://{settings.INSTANCE_DOMAIN}/nodeinfo/2.0"
            }
        ]
    }

@app.get("/nodeinfo/2.0")
async def nodeinfo_2_0():
    """Informations détaillées sur l'instance pour la fédération"""
    return {
        "version": "2.0",
        "software": {
            "name": "revolt-federated",
            "version": "1.0.0"
        },
        "protocols": ["activitypub"],
        "services": {
            "outbound": [],
            "inbound": []
        },
        "usage": {
            "users": {
                "total": 1,  # À calculer dynamiquement
                "activeMonth": 1,
                "activeHalfyear": 1
            },
            "localPosts": 0,  # À calculer dynamiquement
            "localComments": 0
        },
        "openRegistrations": True,
        "metadata": {
            "nodeName": settings.INSTANCE_NAME,
            "nodeDescription": settings.INSTANCE_DESCRIPTION
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )