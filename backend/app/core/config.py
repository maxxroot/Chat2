"""
Configuration de l'application avec support pour la fédération
"""

from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Base de données
    MONGO_URL: str = "mongodb://127.0.0.1:27017"
    DATABASE_NAME: str = "revolt_federated"
    
    # Redis pour le cache et les sessions
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    
    # JWT Configuration
    JWT_SECRET_KEY: str = "your-super-secure-jwt-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    
    # Configuration de l'instance fédérée
    INSTANCE_DOMAIN: str = "localhost:8001"
    INSTANCE_NAME: str = "Revolt Federated Instance"
    INSTANCE_DESCRIPTION: str = "A federated Revolt chat instance"
    ADMIN_EMAIL: str = "admin@localhost"
    FEDERATION_ENABLED: bool = True
    
    # Configuration des fichiers
    FILE_UPLOAD_MAX_SIZE: int = 50000000  # 50MB
    ALLOWED_FILE_TYPES: List[str] = [
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/webm", "audio/mp3", "audio/wav",
        "application/pdf"
    ]
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # ActivityPub Configuration
    ACTIVITYPUB_PUBLIC_KEY: Optional[str] = None
    ACTIVITYPUB_PRIVATE_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"

# Instance globale des paramètres
settings = Settings()