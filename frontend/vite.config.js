import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + uploaded media to the FastAPI backend on :8000,
// so the frontend can use same-origin relative URLs (no CORS in dev).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
