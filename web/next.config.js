/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api-backend/:path*", destination: `${backendUrl.replace(/\/$/, "")}/:path*` },
    ];
  },
};

module.exports = nextConfig;
