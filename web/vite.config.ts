import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the FastAPI backend runs on :8000; in production it serves web/dist itself.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
    },
  },
  build: { outDir: "dist" },
});
