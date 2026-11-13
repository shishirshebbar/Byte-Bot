import { defineConfig } from 'vite';
const target = process.env.BYTEBOT_API_TARGET || 'http://127.0.0.1:8000';
export default defineConfig({
  server: { host: '127.0.0.1', port: 5174, strictPort: true, proxy: { '/api': target } },
  preview: { host: '127.0.0.1', port: 4174, strictPort: true, proxy: { '/api': target } },
});
