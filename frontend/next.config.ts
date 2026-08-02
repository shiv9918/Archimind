import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this project -- without it, Next.js can pick up
  // an unrelated lockfile from the parent home directory and misinfer the root.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
