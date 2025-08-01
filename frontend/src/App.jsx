import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'
import './App.css'

// Configuration API
const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'

// Configuration Axios
axios.defaults.baseURL = `${API_BASE_URL}/api`

// Hook pour l'authentification
const useAuth = () => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('revolt_token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      
      // Vérifier le token au démarrage
      axios.get('/auth/me')
        .then(response => {
          setUser(response.data)
        })
        .catch(() => {
          // Token invalide
          logout()
        })
        .finally(() => {
          setLoading(false)
        })
    } else {
      setLoading(false)
    }
  }, [token])

  const login = async (loginData) => {
    try {
      const response = await axios.post('/auth/login', loginData)
      const { user, token } = response.data
      
      setUser(user)
      setToken(token)
      localStorage.setItem('revolt_token', token)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      
      return { success: true }
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Erreur de connexion' 
      }
    }
  }

  const register = async (registerData) => {
    try {
      const response = await axios.post('/auth/register', registerData)
      const { user, token } = response.data
      
      setUser(user)
      setToken(token)
      localStorage.setItem('revolt_token', token)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      
      return { success: true }
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Erreur d\'inscription' 
      }
    }
  }

  const logout = () => {
    setUser(null)
    setToken(null)
    localStorage.removeItem('revolt_token')
    delete axios.defaults.headers.common['Authorization']
  }

  return { user, token, login, register, logout, loading }
}

// Composant de connexion
const LoginForm = ({ onLogin, onRegister }) => {
  const [isLogin, setIsLogin] = useState(true)
  const [formData, setFormData] = useState({
    login: '',
    password: '',
    username: '',
    email: '',
    display_name: ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    const result = isLogin 
      ? await onLogin({ login: formData.login, password: formData.password })
      : await onRegister({
          username: formData.username,
          email: formData.email,
          password: formData.password,
          display_name: formData.display_name
        })

    if (!result.success) {
      setError(result.error)
    }
    
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {isLogin ? 'Connexion' : 'Inscription'}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Revolt Fédéré - Instance décentralisée
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="rounded-md shadow-sm -space-y-px">
            {isLogin ? (
              <input
                type="text"
                required
                className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Nom d'utilisateur ou email"
                value={formData.login}
                onChange={(e) => setFormData(prev => ({ ...prev, login: e.target.value }))}
              />
            ) : (
              <>
                <input
                  type="text"
                  required
                  className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder="Nom d'utilisateur"
                  value={formData.username}
                  onChange={(e) => setFormData(prev => ({ ...prev, username: e.target.value }))}
                />
                <input
                  type="email"
                  required
                  className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder="Adresse email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                />
                <input
                  type="text"
                  className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder="Nom d'affichage (optionnel)"
                  value={formData.display_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, display_name: e.target.value }))}
                />
              </>
            )}
            
            <input
              type="password"
              required
              className="relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="Mot de passe"
              value={formData.password}
              onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
            />
          </div>

          {error && (
            <div className="text-red-600 text-sm text-center">
              {error}
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {loading ? 'Chargement...' : (isLogin ? 'Se connecter' : 'S\'inscrire')}
            </button>
          </div>

          <div className="text-center">
            <button
              type="button"
              className="text-indigo-600 hover:text-indigo-500"
              onClick={() => setIsLogin(!isLogin)}
            >
              {isLogin ? 'Créer un compte' : 'Déjà un compte ? Se connecter'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Composant principal de chat
const ChatInterface = ({ user, onLogout }) => {
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [channels, setChannels] = useState([])
  const [currentChannel, setCurrentChannel] = useState(null)
  const [loading, setLoading] = useState(false)

  // Simuler un canal général par défaut
  useEffect(() => {
    // Créer un canal DM avec soi-même pour tester
    const createDMChannel = async () => {
      try {
        const response = await axios.post('/channels', {
          channel_type: 'dm',
          recipients: [user.id]
        })
        setCurrentChannel(response.data)
        setChannels([response.data])
      } catch (error) {
        console.error('Erreur lors de la création du canal:', error)
      }
    }

    createDMChannel()
  }, [user])

  // Charger les messages du canal actuel
  useEffect(() => {
    if (currentChannel) {
      loadMessages()
    }
  }, [currentChannel])

  const loadMessages = async () => {
    if (!currentChannel) return
    
    try {
      const response = await axios.get(`/messages/${currentChannel.id}`)
      setMessages(response.data)
    } catch (error) {
      console.error('Erreur lors du chargement des messages:', error)
    }
  }

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!newMessage.trim() || !currentChannel) return

    setLoading(true)
    try {
      const response = await axios.post(`/messages/${currentChannel.id}`, {
        content: newMessage
      })
      
      setMessages(prev => [...prev, response.data])
      setNewMessage('')
    } catch (error) {
      console.error('Erreur lors de l\'envoi du message:', error)
    }
    setLoading(false)
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-gray-800 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold">Revolt Fédéré</h1>
          <p className="text-sm text-gray-300">@{user.username}#{user.discriminator}</p>
        </div>
        
        <div className="flex-1 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-2">CANAUX</h2>
          {channels.map(channel => (
            <div
              key={channel.id}
              className={`p-2 rounded cursor-pointer ${
                currentChannel?.id === channel.id ? 'bg-gray-600' : 'hover:bg-gray-700'
              }`}
              onClick={() => setCurrentChannel(channel)}
            >
              # {channel.name || 'Messages privés'}
            </div>
          ))}
        </div>
        
        <div className="p-4 border-t border-gray-700">
          <button
            onClick={onLogout}
            className="w-full text-left text-red-400 hover:text-red-300"
          >
            Déconnexion
          </button>
        </div>
      </div>

      {/* Zone de chat */}
      <div className="flex-1 flex flex-col">
        {currentChannel ? (
          <>
            {/* En-tête du canal */}
            <div className="bg-white border-b border-gray-200 px-6 py-4">
              <h2 className="text-xl font-semibold">
                # {currentChannel.name || 'Messages privés'}
              </h2>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.map((message, index) => (
                <div key={message.id || index} className="flex space-x-3">
                  <div className="w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-white text-sm font-semibold">
                    {user.username[0].toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold">{user.display_name || user.username}</span>
                      <span className="text-sm text-gray-500">
                        {new Date(message.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-gray-800 mt-1">{message.content}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Zone de saisie */}
            <div className="bg-white border-t border-gray-200 p-4">
              <form onSubmit={sendMessage} className="flex space-x-4">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder={`Message ${currentChannel.name || 'privé'}...`}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !newMessage.trim()}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  Envoyer
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-gray-500">Sélectionnez un canal pour commencer</p>
          </div>
        )}
      </div>
    </div>
  )
}

// Composant principal
const App = () => {
  const { user, login, register, logout, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4">Chargement...</p>
        </div>
      </div>
    )
  }

  return (
    <Router>
      <div className="App">
        {user ? (
          <ChatInterface user={user} onLogout={logout} />
        ) : (
          <LoginForm onLogin={login} onRegister={register} />
        )}
      </div>
    </Router>
  )
}

export default App