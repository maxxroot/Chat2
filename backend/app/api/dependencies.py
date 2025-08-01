"""
Dépendances communes pour les endpoints
"""

from fastapi import Request
from ..core.database import Database
from ..core.federation import FederationManager

async def get_db(request: Request):
    """Dépendance pour récupérer la base de données"""
    return request.app.state.db

async def get_federation_manager(request: Request):
    """Dépendance pour récupérer le gestionnaire de fédération"""
    return request.app.state.federation