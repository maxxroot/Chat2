"""
Système d'authentification JWT avec support pour la fédération
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from nanoid import generate

from .config import settings
from .database import Database

# Configuration du hashage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration du Bearer token
security = HTTPBearer()

class AuthManager:
    def __init__(self):
        self.pwd_context = pwd_context
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Vérifier un mot de passe"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hasher un mot de passe"""
        return self.pwd_context.hash(password)
    
    def generate_discriminator(self) -> str:
        """Générer un discriminateur à 4 chiffres"""
        return f"{secrets.randbelow(9999):04d}"
    
    def generate_session_token(self) -> str:
        """Générer un token de session unique"""
        return generate(size=64)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Créer un token JWT"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Vérifier et décoder un token JWT"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError:
            return None
    
    async def create_session(self, db: Database, user_id: str, user_agent: Optional[str] = None) -> Dict[str, Any]:
        """Créer une session utilisateur"""
        session_token = self.generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        
        session_data = {
            "_id": generate(),
            "token": session_token,
            "user_id": user_id,
            "user_agent": user_agent,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "last_used": datetime.now(timezone.utc)
        }
        
        await db.sessions.insert_one(session_data)
        
        # Créer le JWT
        jwt_token = self.create_access_token(
            data={"sub": user_id, "session_id": session_data["_id"]},
            expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        )
        
        return {
            "token": jwt_token,
            "expires_at": expires_at,
            "session_id": session_data["_id"]
        }
    
    async def revoke_session(self, db: Database, session_id: str) -> bool:
        """Révoquer une session"""
        result = await db.sessions.delete_one({"_id": session_id})
        return result.deleted_count > 0
    
    async def revoke_all_sessions(self, db: Database, user_id: str) -> int:
        """Révoquer toutes les sessions d'un utilisateur"""
        result = await db.sessions.delete_many({"user_id": user_id})
        return result.deleted_count
    
    async def get_current_user(self, db: Database, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """Récupérer l'utilisateur actuel à partir du token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = self.verify_token(credentials.credentials)
            if payload is None:
                raise credentials_exception
            
            user_id: str = payload.get("sub")
            session_id: str = payload.get("session_id")
            
            if user_id is None or session_id is None:
                raise credentials_exception
                
        except JWTError:
            raise credentials_exception
        
        # Vérifier que la session existe encore
        session = await db.sessions.find_one({"_id": session_id, "user_id": user_id})
        if session is None:
            raise credentials_exception
        
        # Vérifier que la session n'a pas expiré
        if session["expires_at"] < datetime.now(timezone.utc):
            await db.sessions.delete_one({"_id": session_id})
            raise credentials_exception
        
        # Récupérer l'utilisateur
        user = await db.get_user_by_id(user_id)
        if user is None:
            raise credentials_exception
        
        # Mettre à jour la dernière utilisation de la session
        await db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"last_used": datetime.now(timezone.utc)}}
        )
        
        return user

# Instance globale du gestionnaire d'authentification
auth_manager = AuthManager()

# Dépendance pour récupérer l'utilisateur actuel
async def get_current_user(db: Database, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    return await auth_manager.get_current_user(db, credentials)

# Dépendance pour récupérer l'utilisateur actuel (optionnel)
async def get_current_user_optional(db: Database, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    if credentials is None:
        return None
    
    try:
        return await auth_manager.get_current_user(db, credentials)
    except HTTPException:
        return None