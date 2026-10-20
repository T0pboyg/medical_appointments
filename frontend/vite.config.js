import { defineConfig } from "vite";

export default defineConfig({
  server: {
    headers: {
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "X-Frame-Options": "DENY",
      "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
      "Content-Security-Policy": [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self' ws://localhost:5173",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
      ].join("; "),
    },
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