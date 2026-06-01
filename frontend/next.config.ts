import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],

  experimental: {
    // Raise the Server Actions body size limit so future server-action-based
    // uploads aren't silently rejected. The KB proxy route is a Route Handler
    // (not a Server Action) so its limit is governed by the hosting platform.
    // On Vercel, Route Handlers are capped at 4.5 MB by default — for larger
    // PDF uploads in production consider switching to direct pre-signed uploads.
    serverActions: {
      bodySizeLimit: "20mb",
    },
  },
};

export default nextConfig;
