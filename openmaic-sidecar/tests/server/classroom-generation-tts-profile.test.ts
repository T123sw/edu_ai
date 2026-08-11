import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, test } from 'vitest';

describe('generate-classroom TTS profile contract', () => {
  test('the route allowlists profile fields without accepting TTS secrets', () => {
    const route = readFileSync(
      fileURLToPath(new URL('../../app/api/generate-classroom/route.ts', import.meta.url)),
      'utf8',
    );

    expect(route).toContain('ttsProviderId');
    expect(route).toContain('ttsVoice');
    expect(route).toContain('ttsSpeed');
    expect(route).not.toContain('ttsApiKey');
    expect(route).not.toContain('ttsBaseUrl');
  });

  test('classroom generation passes the explicit profile into bulk TTS', () => {
    const generation = readFileSync(
      fileURLToPath(new URL('../../lib/server/classroom-generation.ts', import.meta.url)),
      'utf8',
    );

    expect(generation).toMatch(/generateTTSForClassroom\([\s\S]*ttsProviderId/);
    expect(generation).toMatch(/providerId:\s*input\.ttsProviderId/);
    expect(generation).toMatch(/voice:\s*input\.ttsVoice/);
    expect(generation).toMatch(/speed:\s*input\.ttsSpeed/);
  });
});
