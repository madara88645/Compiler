import type { NextConfig } from "next";

const allowedRevalidateHeaderKeys =
  process.env.NODE_ENV === "development"
    ? ["x-revalidate-token", "x-next-revalidate-token"]
    : ["x-revalidate-token"];

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    allowedRevalidateHeaderKeys,
  },
};

export default nextConfig;
