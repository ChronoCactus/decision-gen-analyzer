declare module "next-pwa" {
  import { NextConfig } from "next";

  interface PWAConfig {
    dest?: string;
    disable?: boolean;
    register?: boolean;
    skipWaiting?: boolean;
    reloadOnOnline?: boolean;
    runtimeCaching?: Array<{
      urlPattern: RegExp | string;
      handler: "NetworkFirst" | "CacheFirst" | "StaleWhileRevalidate" | "NetworkOnly" | "CacheOnly";
      options?: {
        cacheName?: string;
        expiration?: {
          maxEntries?: number;
          maxAgeSeconds?: number;
        };
        networkTimeoutSeconds?: number;
      };
    }>;
  }

  export default function withPWA(config: PWAConfig): (nextConfig: NextConfig) => NextConfig;
}
