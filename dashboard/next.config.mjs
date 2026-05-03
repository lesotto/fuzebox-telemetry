/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  env: {
    COSIGNER_URL: process.env.COSIGNER_URL ?? 'http://localhost:8080',
  },
};
export default nextConfig;
