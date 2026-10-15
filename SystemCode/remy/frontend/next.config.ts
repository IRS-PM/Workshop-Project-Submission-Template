import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the Docker image (see Dockerfile).
  output: "standalone",
  // Pin the workspace root: a stray package-lock.json in the home directory
  // sits above this project and would otherwise be inferred as the root.
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    const remyApiUrl = process.env.REMY_API_URL ?? "http://localhost:8081";
    return [{
      source: "/api/v1/:path*",
      destination: `${remyApiUrl}/api/v1/:path*`,
    }];
  },
};

export default nextConfig;
