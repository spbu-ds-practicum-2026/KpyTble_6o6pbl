import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const gatewayUrl =
  process.env.GATEWAY_URL?.trim() || "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: gatewayUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, "")
      },
      "/ws": {
        target: gatewayUrl,
        changeOrigin: true,
        ws: true
      },
      // У Rutube нет CORS для браузерного fetch, поэтому названия тянем
      // через локальный прокси Vite.
      "/rutube-api": {
        target: "https://rutube.ru/api",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/rutube-api/, "")
      }
    }
  }
});