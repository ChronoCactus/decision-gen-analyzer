import type { NextConfig } from "next";
import packageJson from "./package.json";
import withPWAInit from "next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  skipWaiting: true,
  reloadOnOnline: true,
  // Workbox options for caching strategy
  runtimeCaching: [
    {
      urlPattern: /^https?.*/, // Cache all network requests
      handler: "NetworkFirst",
      options: {
        cacheName: "offlineCache",
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        },
        networkTimeoutSeconds: 10,
      },
    },
  ],
});

const nextConfig: NextConfig = {
  /* config options here */
  env: {
    // Version is injected at Docker build time via NEXT_PUBLIC_APP_VERSION build arg
    // For local development, falls back to package.json version
    NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || packageJson.version,
  },
  // Turbopack config to silence webpack config warning from next-pwa
  turbopack: {},
};

export default withPWA(nextConfig);
