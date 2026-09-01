import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /const \[pendingVideos,\s*setPendingVideos\] = useState<[\s\S]*>\(\[\]\);/,
  'ChatPanel should track pending chat videos before send',
);

assert.match(
  chatPanelFile,
  /uploadChatVideosV2\(/,
  'ChatPanel should upload selected videos before sending the reply request',
);

assert.match(
  chatPanelFile,
  /type="file"[\s\S]*accept="video\/mp4,video\/webm,video\/quicktime,video\/x-m4v"/,
  'ChatPanel should expose a video picker for common video types',
);

assert.match(
  chatPanelFile,
  /pendingVideos\.map\(\(video\) =>\s*(\(|\{)/,
  'ChatPanel should render pending video cards before send',
);

assert.match(
  chatPanelFile,
  /setPendingVideos\(\(current\) => current\.filter\(\(video\) => video\.video_id !== videoId\)\)/,
  'ChatPanel should allow removing a pending video before send',
);

const chatServiceFile = readFileSync(
  new URL('../../src/services/teacher/chatV2.ts', import.meta.url),
  'utf8',
);

assert.match(
  chatServiceFile,
  /export interface ChatInputVideoV2 \{/,
  'chatV2 service should expose the chat video metadata contract',
);

assert.match(
  chatServiceFile,
  /input_videos\?: ChatInputVideoV2\[\];/,
  'chatV2 reply payload should carry uploaded video references',
);

assert.match(
  chatServiceFile,
  /export async function uploadChatVideosV2\(/,
  'chatV2 service should expose a chat video upload helper',
);

assert.match(
  chatServiceFile,
  /payload\.input_videos = options\.inputVideos;/,
  'buildChatReplyPayload should include uploaded chat videos in the reply payload',
);

console.log('chatPanel.video-input tests passed');
