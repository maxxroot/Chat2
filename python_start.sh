#!/usr/bin/env bash
# Script de démarrage pour le backend Python FastAPI

set -e

echo "🚀 Démarrage du backend Revolt 100% Python"

# Se déplacer dans le répertoire backend
cd /app/backend

# Vérifier que les dépendances sont installées
echo "📦 Vérification des dépendances Python..."
pip install -r requirements.txt

# Vérifier la connexion MongoDB
echo "🔍 Vérification de MongoDB..."
python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_mongo():
    client = AsyncIOMotorClient('mongodb://127.0.0.1:27017')
    try:
        await client.admin.command('ping')
        print('✅ MongoDB connecté')
    except Exception as e:
        print(f'❌ Erreur MongoDB: {e}')
        exit(1)
    finally:
        client.close()

asyncio.run(test_mongo())
"

# Démarrer le serveur
echo "🚀 Lancement du serveur FastAPI..."
echo "📍 Backend accessible sur: http://localhost:8001"
echo "🔗 Frontend accessible sur: http://localhost:3000"
echo ""

# Lancer le serveur avec uvicorn
python server.py