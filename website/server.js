'use strict';

/**
 * Zedd Weather — static site server
 * ---------------------------------
 * Minimal zero-dependency Node.js static file server, built for GoDaddy
 * Node.js Hosting:
 *   - Listens on process.env.PORT (assigned by the platform; 3000 fallback).
 *   - Serves the folder this file lives in.
 *   - Falls back to index.html for directory requests and SPA-ish routes.
 *
 * Usage:
 *   npm start   (or)   node server.js
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '0.0.0.0';

// Directory that holds this file (works whether started from the site root or not).
const ROOT = __dirname;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.pdf': 'application/pdf',
};

function send(res, status, body, headers) {
  res.writeHead(status, Object.assign({ 'Content-Type': 'text/plain; charset=utf-8' }, headers || {}));
  res.end(body);
}

function serveFile(res, filePath) {
  fs.stat(filePath, (statErr, stats) => {
    if (statErr || !stats.isFile()) {
      return send(res, 404, '404 Not Found');
    }
    const ext = path.extname(filePath).toLowerCase();
    const type = MIME[ext] || 'application/octet-stream';
    const stream = fs.createReadStream(filePath);
    res.writeHead(200, { 'Content-Type': type });
    stream.pipe(res);
  });
}

function resolvePath(urlPath) {
  // Decode and strip query string.
  let clean = decodeURIComponent(urlPath.split('?')[0]);
  // Treat bare requests as the home page.
  if (clean === '/' || clean === '') clean = '/index.html';

  const absolute = path.normalize(path.join(ROOT, clean));

  // Guard against path traversal outside the site root.
  if (!absolute.startsWith(ROOT + path.sep)) return null;

  if (fs.existsSync(absolute) && fs.statSync(absolute).isDirectory()) {
    // If the directory has an index.html, serve it.
    const indexFile = path.join(absolute, 'index.html');
    if (fs.existsSync(indexFile)) return indexFile;
    // SPA fallback: unknown routes render the home page.
    return path.join(ROOT, 'index.html');
  }

  return absolute;
}

const server = http.createServer((req, res) => {
  const method = (req.method || 'GET').toUpperCase();

  if (method === 'GET' || method === 'HEAD') {
    const filePath = resolvePath(req.url);
    if (!filePath) return send(res, 400, 'Bad Request');
    serveFile(res, filePath);
    return;
  }

  if (method === 'OPTIONS') {
    res.writeHead(204, { Allow: 'GET, HEAD, OPTIONS' });
    return res.end();
  }

  send(res, 405, 'Method Not Allowed');
});

server.listen(PORT, HOST, () => {
  // eslint-disable-next-line no-console
  console.log(`Zedd Weather site running at http://${HOST}:${PORT}`);
});
