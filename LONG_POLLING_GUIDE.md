# Long Polling API - Guide d'utilisation

Le système de long polling est maintenant implémenté comme alternative au SSE (Server-Sent Events). Il permet aux clients de recevoir des événements temps réel via des requêtes HTTP standards.

## Endpoints disponibles

### 1. Long polling général
```
GET /api/poll/poll
```

**Paramètres de query :**
- `last_event_id` (optionnel) : Dernier ID d'événement reçu
- `timeout` (défaut: 30s, max: 60s) : Durée d'attente en secondes
- `channels` (optionnel) : IDs des canaux séparés par des virgules
- `servers` (optionnel) : IDs des serveurs séparés par des virgules

**Headers requis :**
- `Authorization: Bearer <token>`

**Exemple de requête :**
```bash
curl -H "Authorization: Bearer <token>" \
     "http://localhost:8001/api/poll/poll?timeout=30&channels=channel1,channel2"
```

**Réponse :**
```json
{
  "events": [
    {
      "id": "event_id_123",
      "type": "message_created",
      "data": {...},
      "timestamp": "2025-01-16T15:30:00Z",
      "channel_id": "channel1",
      "server_id": "server1"
    }
  ],
  "timestamp": "2025-01-16T15:30:00Z",
  "has_more": true
}
```

### 2. Long polling par canal
```
GET /api/poll/poll/channel/{channel_id}
```

Écoute uniquement les événements d'un canal spécifique.

### 3. Long polling par serveur
```
GET /api/poll/poll/server/{server_id}
```

Écoute uniquement les événements d'un serveur spécifique.

### 4. Statistiques (admin uniquement)
```
GET /api/poll/stats
```

### 5. Nettoyage manuel (admin uniquement)
```
POST /api/poll/cleanup?max_age_hours=24
```

## Types d'événements supportés

- `message_created` : Nouveau message
- `message_updated` : Message modifié
- `message_deleted` : Message supprimé
- `user_status_changed` : Changement de statut utilisateur
- `typing_indicator` : Indicateur de frappe
- `server_member_joined` : Membre rejoint le serveur
- `server_member_left` : Membre quitté le serveur

## Utilisation côté client (JavaScript)

```javascript
class LongPollingClient {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.token = token;
    this.lastEventId = null;
    this.isPolling = false;
  }

  async startPolling(channels = [], servers = []) {
    this.isPolling = true;
    
    while (this.isPolling) {
      try {
        const params = new URLSearchParams({
          timeout: '30',
          ...(this.lastEventId && { last_event_id: this.lastEventId }),
          ...(channels.length && { channels: channels.join(',') }),
          ...(servers.length && { servers: servers.join(',') })
        });

        const response = await fetch(`${this.baseUrl}/api/poll/poll?${params}`, {
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        
        // Traiter les événements
        for (const event of data.events) {
          this.handleEvent(event);
          this.lastEventId = event.id;
        }

      } catch (error) {
        console.error('Erreur de long polling:', error);
        await new Promise(resolve => setTimeout(resolve, 5000)); // Attendre 5s avant retry
      }
    }
  }

  handleEvent(event) {
    console.log('Nouvel événement:', event);
    
    switch (event.type) {
      case 'message_created':
        // Ajouter le message à l'interface
        break;
      case 'message_updated':
        // Mettre à jour le message
        break;
      case 'message_deleted':
        // Supprimer le message de l'interface
        break;
      // ... autres types
    }
  }

  stopPolling() {
    this.isPolling = false;
  }
}

// Utilisation
const client = new LongPollingClient('http://localhost:8001', 'your-token');
client.startPolling(['channel1', 'channel2'], ['server1']);
```

## Avantages du Long Polling vs SSE

**Long Polling :**
- ✅ Compatible avec tous les navigateurs et proxies
- ✅ Fonctionne à travers les firewalls
- ✅ Contrôle précis des timeouts
- ✅ Gestion plus simple des erreurs de réseau
- ❌ Plus de surcharge HTTP (headers, handshake)

**SSE (Server-Sent Events) :**
- ✅ Plus efficace pour les connexions longues
- ✅ Moins de surcharge réseau
- ✅ Reconnexion automatique
- ❌ Problèmes avec certains proxies/firewalls
- ❌ Limité à 6 connexions par domaine

## Implémentation hybride

Le backend émet maintenant les événements à la fois via SSE et Long Polling, permettant aux clients de choisir la méthode qui leur convient le mieux.

## Performance et limitations

- **Timeout max :** 60 secondes par requête
- **Nettoyage automatique :** Les événements plus anciens que 24h sont supprimés automatiquement
- **Limite d'événements :** Max 100 événements par file d'attente
- **Connexions simultanées :** Pas de limite hard-codée, mais supervisé via `/api/poll/stats`