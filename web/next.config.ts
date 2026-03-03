import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    allowedRevalidateHeaderKeys: ['*']
  }
};

export default nextConfig;
