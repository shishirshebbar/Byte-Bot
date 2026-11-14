import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { test } from 'node:test';
import { createApp } from './server.mjs';

test('same-origin proxy preserves session cookies and API responses', async () => {
  const backend = createServer((request, response) => {
    if (request.url === '/api/v1/transactions') {
      response.writeHead(200, {
        'Content-Type': 'application/json',
        'Set-Cookie': 'bytebot_session=synthetic; HttpOnly; SameSite=Lax; Path=/',
      });
      response.end('{"transactions":[]}');
    } else if (request.url === '/api/v1/transactions/example') {
      response.writeHead(request.headers.cookie === 'bytebot_session=synthetic' ? 200 : 404, {
        'Content-Type': 'application/json',
      });
      response.end('{"id":"example"}');
    } else if (request.url === '/api/v1/claim-check' && request.method === 'POST') {
      const chunks = [];
      request.on('data', chunk => chunks.push(chunk));
      request.on('end', () => {
        response.writeHead(request.headers.cookie === 'bytebot_session=synthetic' ? 200 : 404, {
          'Content-Type': 'application/json',
        });
        response.end(JSON.stringify({ status: 'checked', body: JSON.parse(Buffer.concat(chunks).toString()) }));
      });
    } else {
      response.writeHead(404, { 'Content-Type': 'application/json' });
      response.end('{"error":"not found"}');
    }
  });
  backend.listen(8000, '::1');
  await once(backend, 'listening');
  let frontend;
  try {
    frontend = createApp('http://[::1]:8000').listen(4174, '127.0.0.1');
    await once(frontend, 'listening');
    const root = 'http://127.0.0.1:4174';
    const transactions = await fetch(`${root}/api/v1/transactions`);
    assert.deepEqual(await transactions.json(), { transactions: [] });
    const cookie = transactions.headers.get('set-cookie').split(';')[0];
    const foreign = await fetch(`${root}/api/v1/transactions/example`);
    assert.equal(foreign.status, 404);
    const detail = await fetch(`${root}/api/v1/transactions/example`, { headers: { Cookie: cookie } });
    assert.equal(detail.status, 200);
    assert.deepEqual(await detail.json(), { id: 'example' });
    const claim = await fetch(`${root}/api/v1/claim-check`, {
      method: 'POST', headers: { Cookie: cookie, 'Content-Type': 'application/json' }, body: '{"amount_paise":500000}',
    });
    assert.equal(claim.status, 200);
    assert.deepEqual(await claim.json(), { status: 'checked', body: { amount_paise: 500000 } });
    const missing = await fetch(`${root}/api/v1/missing`);
    assert.equal(missing.status, 404);
    assert.match(missing.headers.get('content-type'), /application\/json/);
    const page = await fetch(`${root}/transactions/example`, { headers: { Accept: 'text/html' } });
    assert.equal(page.status, 200);
    assert.match(page.headers.get('content-type'), /text\/html/);
    assert.match(page.headers.get('content-security-policy'), /connect-src 'self'/);
    const asset = await fetch(`${root}/missing.js`);
    assert.equal(asset.status, 404);
    await new Promise(resolve => backend.close(resolve));
    const unavailable = await fetch(`${root}/api/v1/transactions`);
    assert.equal(unavailable.status, 502);
    assert.equal((await unavailable.json()).error.code, 'api_unavailable');
  } finally {
    if (frontend) await new Promise(resolve => frontend.close(resolve));
    if (backend.listening) await new Promise(resolve => backend.close(resolve));
  }
});
