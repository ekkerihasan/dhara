import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false, // keep the screen clean when sharing it in a demo
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
