import assert from 'node:assert/strict';

import { resolvePptAssetUrl } from '../../src/services/teacher/pptAssets.ts';

const previousWindow = (globalThis as any).window;

(globalThis as any).window = {
  location: {
    origin: 'https://edu.example.com',
    hostname: 'edu.example.com',
  },
};

assert.equal(
  resolvePptAssetUrl('/ppt/artifacts/job_001/rev_0000/deck.html'),
  'https://edu.example.com/ppt/artifacts/job_001/rev_0000/deck.html',
);

assert.equal(
  resolvePptAssetUrl('http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.html'),
  'https://edu.example.com/ppt/artifacts/job_001/rev_0000/deck.html',
);

assert.equal(
  resolvePptAssetUrl('http://127.0.0.1:46080/assets/HEU/heu-logo.png'),
  'https://edu.example.com/assets/HEU/heu-logo.png',
);

(globalThis as any).window = {
  location: {
    origin: 'http://127.0.0.1:5173',
    hostname: '127.0.0.1',
  },
};

assert.equal(
  resolvePptAssetUrl('http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.html'),
  'http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0000/deck.html',
);

if (previousWindow === undefined) {
  delete (globalThis as any).window;
} else {
  (globalThis as any).window = previousWindow;
}

console.log('pptAssets tests passed');
