var _a;
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
var gatewayUrl = ((_a = process.env.GATEWAY_URL) === null || _a === void 0 ? void 0 : _a.trim()) || "http://localhost:8080";
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: gatewayUrl,
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/api/, ""); }
            },
            "/ws": {
                target: gatewayUrl,
                changeOrigin: true,
                ws: true
            },
            "/rutube-api": {
                target: "https://rutube.ru/api",
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/rutube-api/, ""); }
            }
        }
    }
});
