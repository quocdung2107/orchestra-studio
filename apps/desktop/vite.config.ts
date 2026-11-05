import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const BACKEND = `http://127.0.0.1:${process.env.ORCHESTRA_PORT ?? "8765"}`;
const TOKEN_FILE = resolve(__dirname, "../../data/backend-token");

// ADR-0009: the dev proxy injects the per-launch token, so the browser never holds it.
function readToken(): string {
  try {
    return readFileSync(process.env.ORCHESTRA_TOKEN_FILE ?? TOKEN_FILE, "utf8").trim();
  } catch {
    return "";
  }
}

const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "frame-ancestors 'none'",
].join("; ");

export default defineConfig(({ command }) => ({
  root: "renderer",
  base: "./",
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "orchestra-csp",
      transformIndexHtml(html: string) {
        // Strict CSP only for production builds; Vite dev needs inline HMR scripts.
        if (command !== "build") return html;
        return html.replace(
          "<head>",
          `<head>\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`,
        );
      },
    },
  ],
  server: {
    port: 5173,
    strictPort: true,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: BACKEND,
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (req) => {
            req.setHeader("x-orchestra-token", readToken());
          });
        },
      },
    },
  },
  build: { outDir: "../dist/renderer", emptyOutDir: true },
  test: {
    root: ".",
    environment: "jsdom",
    include: ["renderer/src/**/*.test.{ts,tsx}"],
  },
}));
