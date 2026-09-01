import assert from 'node:assert/strict';

const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];

const originalFetch = globalThis.fetch;
const originalWindow = (globalThis as any).window;

(globalThis as any).window = {
  location: { origin: 'http://localhost:5173' },
  localStorage: {
    getItem(key: string) {
      if (key === 'edu-ai-auth') {
        return JSON.stringify({ token: 'token-123' });
      }
      return null;
    },
  },
};

globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  fetchCalls.push({ input, init });
  return new Response(JSON.stringify({ filename: 'voice.webm', text: '识别结果文本' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}) as typeof fetch;

const { transcribeSpeechV2 } = await import('../../src/services/teacher/chatV2.ts');

const result = await transcribeSpeechV2(new Blob(['voice-bytes'], { type: 'audio/webm' }), 'voice.webm');

assert.equal(result.text, '识别结果文本');
assert.equal(fetchCalls.length, 1);
assert.equal(String(fetchCalls[0].input), 'http://localhost:8000/api/speech/transcribe');
assert.equal((fetchCalls[0].init?.method || '').toUpperCase(), 'POST');
assert.equal((fetchCalls[0].init?.headers as Record<string, string>).Authorization, 'Bearer token-123');
assert.ok(fetchCalls[0].init?.body instanceof FormData);

globalThis.fetch = (async () =>
  new Response(JSON.stringify({ detail: 'Missing Baidu speech credentials.' }), {
    status: 503,
    statusText: 'Service Unavailable',
    headers: { 'Content-Type': 'application/json' },
  })) as typeof fetch;

await assert.rejects(
  () => transcribeSpeechV2(new Blob(['voice-bytes'], { type: 'audio/webm' }), 'voice.webm'),
  /Missing Baidu speech credentials\./,
);

globalThis.fetch = originalFetch;
(globalThis as any).window = originalWindow;

console.log('chatV2.speech tests passed');
