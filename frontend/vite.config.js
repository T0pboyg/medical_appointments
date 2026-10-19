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
        configure(proxy) {
          proxy.on("proxyReq", (proxyReq, req) => {
            const proxySecret = process.env.API_PROXY_SECRET;

            if (!proxySecret) {
              throw new Error("API_PROXY_SECRET is required");
            }

            proxyReq.setHeader("X-API-Proxy-Secret", proxySecret);
            const clientAddress = req.socket.remoteAddress;

            if (clientAddress) {
              proxyReq.setHeader("X-Forwarded-For", clientAddress);
            } else {
              proxyReq.removeHeader("X-Forwarded-For");
            }
          });
        },
      },
    },
  },
});