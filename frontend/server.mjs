import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const dist = fileURLToPath(new URL('./dist/', import.meta.url));
const csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; " +
  "media-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'";

export function createApp(target = process.env.BYTEBOT_API_TARGET || 'http://127.0.0.1:8000') {
  const url = new URL(target);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) {
    throw new Error('BYTEBOT_API_TARGET must be an HTTP(S) origin without credentials or a path.');
  }
  const app = express();
  app.disable('x-powered-by');
  app.use(createProxyMiddleware({
    target: url.origin,
    changeOrigin: true,
    pathFilter: pathname => pathname === '/api' || pathname.startsWith('/api/'),
    on: {
      error(_error, _request, response) {
        if (!response.headersSent) {
          response.writeHead(502, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
        }
        response.end('{"error":{"code":"api_unavailable","message":"The API is temporarily unavailable."}}');
      },
    },
  }));
  app.use((_request, response, next) => {
    response.set({
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
      'X-Frame-Options': 'DENY',
      'Permissions-Policy': 'microphone=(self), camera=(), geolocation=(), payment=()',
      'Content-Security-Policy': csp,
    });
    next();
  });
  app.use(express.static(dist, { index: false }));
  app.use((request, response) => {
    if ((request.method === 'GET' || request.method === 'HEAD') &&
        request.accepts('html') && !path.extname(request.path)) {
      response.sendFile(path.join(dist, 'index.html'));
    } else {
      response.sendStatus(404);
    }
  });
  return app;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const port = Number(process.env.PORT || 4174);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid PORT.');
  createApp().listen(port, process.env.HOST || '127.0.0.1', () => {
    console.log(`Byte Bot frontend listening on port ${port}`);
  });
}
