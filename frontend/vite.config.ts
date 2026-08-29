import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/auth/get-session': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/auth/verify': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/auth/link-account': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/auth/complete-signup': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      '/auth/set-auth-cookie': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    },
    hmr: {
      overlay: false
    },
    watch: {
      usePolling: true  // Use polling instead of WebSocket for file watching
    }
  },
  build: {
    // Performance optimizations
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
            return 'react-vendor'
          }
          if (id.includes('@clerk')) {
            return 'clerk-vendor'
          }
          if (id.includes('i18next')) {
            return 'i18n-vendor'
          }
        }
      }
    },
    chunkSizeWarningLimit: 1000
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', '@clerk/clerk-react']
  }
})
