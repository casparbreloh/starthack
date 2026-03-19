import tailwindcss from '@tailwindcss/vite'
import viteReact from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [tailwindcss(), viteReact()],
  server: {
    port: 5173,
    proxy: {
      '/sim': 'http://localhost:8000',
      '/weather': 'http://localhost:8000',
      '/energy': 'http://localhost:8000',
      '/greenhouse': 'http://localhost:8000',
      '/water': 'http://localhost:8000',
      '/crops': 'http://localhost:8000',
      '/nutrients': 'http://localhost:8000',
      '/crew': 'http://localhost:8000',
      '/sensors': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/score': 'http://localhost:8000',
      '/agent': 'http://localhost:8000',
    },
  },
})
