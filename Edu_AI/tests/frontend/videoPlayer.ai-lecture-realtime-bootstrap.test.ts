import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(
  page,
  /activeMaterialContent\.source_ppt_material_id/,
  'VideoPlayer should resolve the source PPT from the active AI lecture session metadata',
);
assert.match(
  page,
  /courseMaterialToMarkdown\(sourcePptMaterial \|\| selectedPptMaterial\)/,
  'VideoPlayer should bootstrap the lecture markdown from the selected PPT material',
);
assert.match(
  page,
  /patchAiLectureSessionSnapshot\(course\.id,\s*[A-Za-z0-9_]+,\s*\{[\s\S]*ai_lecturer_course_id:[\s\S]*outline:/s,
  'Creating the AI lecturer outline should persist the session outline snapshot',
);
assert.match(
  page,
  /patchAiLectureSessionSnapshot\(course\.id,\s*[A-Za-z0-9_]+,\s*\{[\s\S]*script:/s,
  'Generating a script should persist slide scripts into the session snapshot',
);
assert.match(
  page,
  /await ensureAiLecturerCourse\(/,
  'Starting realtime playback should ensure the AI lecturer course exists first',
);
assert.match(
  page,
  /await ensureSlideScript\(/,
  'Starting realtime playback should generate the active slide script before speaking',
);
assert.match(
  page,
  /await speakSentence\(/,
  'Starting realtime playback should automatically begin speaking after script generation',
);
assert.match(
  page,
  /autoPlaybackTimerRef = useRef<number \| null>\(null\)/,
  'Realtime playback should track an autoplay timer for continuous sentence playback',
);
assert.match(
  page,
  /function estimateSpeechDurationMs\(sentence: string\)/,
  'Realtime playback should estimate sentence playback time before advancing automatically',
);
assert.match(
  page,
  /const nextSentenceIndex = currentSentenceIndex \+ 1;/,
  'Realtime playback should advance to the next sentence after the current one finishes',
);
assert.match(
  page,
  /const nextSlideIndex = slideIndex \+ 1;/,
  'Realtime playback should advance to the next slide after finishing the current slide script',
);
assert.match(
  page,
  /window\.setTimeout\(\(\) => \{\s*void continueAutoPlayback\(\);\s*\}, estimateSpeechDurationMs\(sentence\)\)/s,
  'Realtime playback should schedule continuous playback after each spoken sentence',
);
assert.match(
  page,
  /const slideScriptsRef = useRef<Record<number, string\[]>>\(\{\}\);/,
  'Realtime autoplay should keep the latest per-slide scripts in a ref so timers do not read a stale render snapshot',
);
assert.match(
  page,
  /const scriptSentencesRef = useRef<string\[]>\(\[\]\);/,
  'Realtime autoplay should keep the latest visible script sentences in a ref for timer-driven playback',
);
assert.match(
  page,
  /const outlineRef = useRef<Slide\[]>\(\[\]\);/,
  'Realtime autoplay should keep the latest outline in a ref for timer-driven slide advancement',
);
assert.match(
  page,
  /const liveSessionId = livetalkingSessionIdRef\.current;/,
  'Realtime autoplay should read the freshest LiveTalking session id from a ref before speaking follow-up sentences',
);
assert.match(
  page,
  /const sentencesOnSlide = slideScriptsRef\.current\[slideIndex\] \|\| \(slideIndex === activeSlideIndexRef\.current \? scriptSentencesRef\.current : \[\]\);/,
  'Realtime autoplay should resolve follow-up sentences from refs instead of stale closure state',
);
assert.match(
  page,
  /const activeLivetalkingSessionId = livetalkingSessionIdOverride \|\| livetalkingSessionId;/,
  'Realtime playback should allow speakSentence to use the just-created LiveTalking session id before React state settles',
);
assert.match(
  page,
  /await speakSentence\(sentences\[0\], 0, nextSlideIndex, sessionId,\s*liveSessionId,\s*\{\s*scheduleAutoAdvance:\s*true\s*\}\)/,
  'Starting realtime playback should pass the freshly returned LiveTalking session id into speakSentence',
);
assert.match(
  page,
  /lastHydratedSessionIdRef/,
  'Realtime playback should track the last hydrated AI lecture session to avoid repeated resets',
);
assert.match(
  page,
  /lastHydratedSessionIdRef\.current === sessionId/,
  'Realtime playback should skip re-hydrating the same AI lecture session repeatedly',
);
assert.doesNotMatch(
  page,
  /\}, \[activeMaterial,/,
  'Realtime playback should not re-hydrate from the whole active material object on every material refresh',
);
assert.doesNotMatch(
  page,
  /<iframe[\s\S]*src=\{selectedPptPreviewUrl\}/s,
  'Realtime playback should no longer render a PPT preview underneath the digital human',
);

console.log('videoPlayer.ai-lecture-realtime-bootstrap tests passed');
