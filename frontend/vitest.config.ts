import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    env: {
      NEXT_PUBLIC_APP_NAME: "ServerPilot",
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
      NEXT_PUBLIC_WS_URL: "ws://localhost:8000",
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
