import type { NextConfig } from "next";

// next.config is serialized at build time, so BACKEND_URL must be set when the
// image is built (not only when the container starts).
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Produces a self-contained server for a small production container image.
  output: "standalone",
  // Proxy API calls so the browser talks to one origin; this keeps the
  // httpOnly session cookie same-site and avoids CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
