import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy all /api calls to the FastAPI backend during dev
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Split the Plotly bundle into its own chunk so the shell loads fast.
    // Plotly weighs ~4.5 MB and is only needed on result/compare pages.
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (
            id.includes("node_modules/plotly.js") ||
            id.includes("node_modules/react-plotly.js")
          ) {
            return "plotly";
          }
          if (id.includes("node_modules/react")) {
            return "react-vendor";
          }
        },
      },
    },
    // Plotly is large by nature; silence the warning.
    chunkSizeWarningLimit: 1024,
  },
});
