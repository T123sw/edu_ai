import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /const \[isRecording,\s*setIsRecording\] = useState\(false\);[\s\S]*const \[isTranscribing,\s*setIsTranscribing\] = useState\(false\);/s,
  'ChatPanel should track recording and transcription status for voice input',
);

assert.match(
  chatPanelFile,
  /transcribeSpeechV2\(/,
  'ChatPanel should send recorded audio to the speech transcription API',
);

assert.match(
  chatPanelFile,
  /resolveSpeechInputError\(/,
  'ChatPanel should still translate browser microphone errors into user-facing messages',
);

assert.doesNotMatch(
  chatPanelFile,
  /audioFileInputRef[\s\S]*type="file"[\s\S]*accept="audio\/\*"/s,
  'ChatPanel should not include a file-upload fallback when no recording device is available',
);

assert.doesNotMatch(
  chatPanelFile,
  /fallback === 'file_upload'[\s\S]*audioFileInputRef\.current\?\.click\(\)/s,
  'ChatPanel should fail explicitly instead of opening a local audio picker when no microphone exists',
);

assert.match(
  chatPanelFile,
  /icon={<AudioOutlined \/>}[\s\S]*录音中|语音输入/s,
  'ChatPanel should render a visible voice input button in the composer',
);

console.log('chatPanel.voice-input tests passed');
