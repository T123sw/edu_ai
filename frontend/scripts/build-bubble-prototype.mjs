/** Build the isolated prototype and a self-contained HTML review artifact. */
import { build } from 'vite';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
process.chdir(frontend);
await build({ configFile: path.join(frontend, 'vite.bubble.config.ts') });
const built = path.resolve(frontend, '../.runtime/bubble-prototype-build');
let html = await readFile(path.join(built, 'bubble-preview.html'), 'utf8');
for (const match of [...html.matchAll(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g)]) {
  const js = await readFile(path.join(built, match[1]), 'utf8');
  html = html.replace(match[0], () => `<script type="module">${js.replaceAll('</script', '<\\/script')}</script>`);
}
for (const match of [...html.matchAll(/<link\b[^>]*href="([^"]+\.css)"[^>]*>/g)]) {
  const css = await readFile(path.join(built, match[1]), 'utf8');
  html = html.replace(match[0], () => `<style>${css}</style>`);
}
const target = path.resolve(frontend, '../docs/acceptance/2026-10-15-bubble-prototype');
await mkdir(target, { recursive: true });
await writeFile(path.join(target, 'bubble-sort-prototype.html'), html);
console.log('Standalone review artifact:', path.join(target, 'bubble-sort-prototype.html'));
