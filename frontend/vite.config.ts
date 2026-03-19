import tailwindcss from "@tailwindcss/vite"
import viteReact from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [tailwindcss(), viteReact()],
  server: {
    port: 5173,
    proxy: {
      "/sim": "http://localhost:8080",
      "/weather": "http://localhost:8080",
      "/energy": "http://localhost:8080",
      "/greenhouse": "http://localhost:8080",
      "/water": "http://localhost:8080",
      "/crops": "http://localhost:8080",
      "/nutrients": "http://localhost:8080",
      "/crew": "http://localhost:8080",
      "/sensors": "http://localhost:8080",
      "/events": "http://localhost:8080",
      "/score": "http://localhost:8080",
      "/agent": "http://localhost:8080",
    },
  },
})
