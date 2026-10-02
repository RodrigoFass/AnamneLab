import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icone-app.svg", "simbolo-claro.svg", "simbolo-escuro.svg"],
      manifest: {
        name: "AnamneLab",
        short_name: "AnamneLab",
        description: "Treino de anamnese com correção na hora.",
        lang: "pt-BR",
        start_url: "/",
        display: "standalone",
        orientation: "portrait",
        theme_color: "#0E5E66",
        background_color: "#F6F3EC",
        icons: [
          { src: "icone-app-192.png", sizes: "192x192", type: "image/png" },
          { src: "icone-app-512.png", sizes: "512x512", type: "image/png" },
          { src: "icone-app.svg", sizes: "any", type: "image/svg+xml" },
        ],
      },
      workbox: {
        // A API nunca entra no cache do service worker: transcrição e nota
        // ficam só no servidor.
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
      },
    }),
  ],
  server: {
    // Endereços públicos do túnel grátis da Cloudflare, para abrir o app no celular com HTTPS
    // (sem HTTPS o celular não libera o microfone).
    allowedHosts: [".trycloudflare.com"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
