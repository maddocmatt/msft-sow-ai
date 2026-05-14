import type { NextConfig } from "next";

// Static HTML export for Azure Static Web Apps.
// SWA serves the `out/` directory and proxies `/api/*` to the linked
// Function App backend (configured in staticwebapp.config.json).
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
