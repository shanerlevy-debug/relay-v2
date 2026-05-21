/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  // The API runs at :8000 in dev; UI at :3000. Proxy /api/* through Next so
  // cookies flow without CORS gymnastics during dev. In prod, nginx handles this.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`
            : "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default config;
