import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0'
  },
  define: {
    'process.env.REACT_APP_BACKEND_URL': JSON.stringify(process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001')
  }
})