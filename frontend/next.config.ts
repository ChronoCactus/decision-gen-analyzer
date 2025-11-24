import type { NextConfig } from "next";
// @ts-ignore - package.json is not typed
import packageJson from "./package.json";

const nextConfig: NextConfig = {
  /* config options here */
  env: {
    // Version is injected at Docker build time via NEXT_PUBLIC_APP_VERSION build arg
    // For local development, falls back to package.json version
    NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || packageJson.version,
  },
};

export default nextConfig;
