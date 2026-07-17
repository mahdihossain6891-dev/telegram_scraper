import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["react-plotly.js"],
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "plotly.js": "plotly.js-dist-min",
    };
    return config;
  },
};

export default nextConfig;
