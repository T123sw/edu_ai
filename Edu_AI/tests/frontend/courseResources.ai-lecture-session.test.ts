import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/CourseResources.tsx', import.meta.url), 'utf8');

assert.match(page, /ai_lecture_session:\s*"AI lecture session"/, 'Course resources should label AI lecture session materials');
assert.match(page, /material_type === "ai_lecture_session"/, 'Course resources should detect AI lecture session materials');
assert.match(page, /recording_url/, 'Course resources should read AI lecture recording URLs');
assert.match(page, /<video controls[\s\S]*src=\{playbackUrl\(recordingUrl\)\}/, 'Course resources should render a playable saved lecture recording');
assert.match(page, /stitch-ai-lecture-session-id/, 'Course resources should preserve the selected AI lecture session when opening the player');
assert.match(page, /can_continue_interactive/, 'Course resources should surface whether a session can continue interactively');

console.log('courseResources.ai-lecture-session tests passed');
