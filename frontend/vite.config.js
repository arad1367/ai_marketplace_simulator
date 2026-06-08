import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During local development, proxy /api to the FastAPI backend so the frontend
// and backend can share an origin (avoids CORS friction). In production the
// frontend talks to the backend via VITE_API_BASE_URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
