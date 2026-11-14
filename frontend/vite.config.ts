import { defineConfig } from 'vite';
const target = process.env.BYTEBOT_API_TARGET || 'http://127.0.0.1:8000';
const headers = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'microphone=(self), camera=(), geolocation=(), payment=()',
};
// The production preview enforces a strict policy. The dev server omits CSP because Vite's HMR injects inline scripts.
const csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; " +
  "media-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'";
export default defineConfig({
  server: { host: '127.0.0.1', port: 5174, strictPort: true, proxy: { '/api': target }, headers },
  preview: { host: '127.0.0.1', port: 4174, strictPort: true, proxy: { '/api': target }, headers: { ...headers, 'Content-Security-Policy': csp } },
});
