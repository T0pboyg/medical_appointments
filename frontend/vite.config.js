import { defineConfig } from "vite";

export default defineConfig({
  server: {
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});