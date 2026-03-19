import tailwindcss from "@tailwindcss/vite"
import viteReact from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [tailwindcss(), viteReact()],
  server: {
    port: 5173,
    proxy: {
      "/simulation": {
        target: "http://localhost:8080",
        rewrite: (path) => path.replace(/^\/simulation/, ""),
      },
    },
  },
})
