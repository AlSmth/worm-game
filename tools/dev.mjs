#!/usr/bin/env node
/**
 * Запуск игры для разработки: сначала собирает графику (если исходники менялись), затем поднимает сервер Vite.
 *   node tools/dev.mjs [--open]
 * Адрес: http://127.0.0.1:5173/
 * Если игра уже запущена (порт занят этим же сервером), новый сервер не поднимается, а просто открывается тот же адрес.
 */
import { exec } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
process.chdir(ROOT);

const OPEN = process.argv.includes('--open');
const URL = 'http://127.0.0.1:5173/';

function openInBrowser(url) {
  const cmd = process.platform === 'win32' ? `start "" "${url}"` : process.platform === 'darwin' ? `open "${url}"` : `xdg-open "${url}"`;
  exec(cmd);
}

await import('./build-assets.mjs');

const server = await createServer({ root: ROOT, server: { open: OPEN } });
try {
  await server.listen();
  server.printUrls();
} catch (e) {
  if (!/already in use/i.test(String(e && e.message))) throw e;
  await server.close();
  console.log(`Игра уже запущена: ${URL}`);
  if (OPEN) openInBrowser(URL);
}
