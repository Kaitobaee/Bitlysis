import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// connect-src: production chỉ cho https:, dev thêm localhost để gọi API local
const connectSrc = isDev
  ? "connect-src 'self' https: http://localhost:* http://127.0.0.1:*"
  : "connect-src 'self' https:";

const securityHeaders = [
  {
    key: "X-DNS-Prefetch-Control",
    value: "on",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  },
  {
    // CSP: cho phép Next.js inline scripts + wasm; strict nhưng functional
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // unsafe-eval cần cho WASM
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' https://fonts.gstatic.com",
      "img-src 'self' data: blob: https:",
      connectSrc,
      "worker-src 'self' blob:",
      "wasm-src 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    devtoolSegmentExplorer: false,
  },
  async headers() {
    return [
      {
        // Áp dụng cho tất cả routes
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
  webpack(config, { isServer }) {
    if (!isServer) {
      config.experiments = { ...config.experiments, asyncWebAssembly: true };
    }
    return config;
  },
};

export default nextConfig;
