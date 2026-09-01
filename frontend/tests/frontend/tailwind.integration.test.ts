import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const packageJson = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')) as {
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
};
const allDeps = {
  ...(packageJson.dependencies || {}),
  ...(packageJson.devDependencies || {}),
};

const stitchStyles = readFileSync(join(root, 'src', 'stitch', 'styles.css'), 'utf8');

assert.match(stitchStyles, /@tailwind\s+utilities;/);
assert.ok(existsSync(join(root, 'tailwind.config.js')), 'tailwind.config.js is required for Stitch utility classes');
assert.ok(existsSync(join(root, 'postcss.config.js')), 'postcss.config.js is required for Vite to run Tailwind');
assert.ok(allDeps.tailwindcss, 'tailwindcss must be declared in package.json');
assert.ok(allDeps.postcss, 'postcss must be declared in package.json');
assert.ok(allDeps.autoprefixer, 'autoprefixer must be declared in package.json');
