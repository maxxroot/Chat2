"""
Routeur principal de l'API
"""

from fastapi import APIRouter
from .endpoints import auth, users, servers, channels, messages, federation

api_router = APIRouter()

# Routes d'authentification
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Routes des entités principales
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(servers.router, prefix="/servers", tags=["servers"])
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])

# Routes de fédération (ActivityPub)
api_router.include_router(federation.router, prefix="/activitypub", tags=["federation"])