import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(file, /viewingFile\.type === 'ppt'/, 'StudioPanel should render a dedicated PPT preview branch');
assert.match(file, /<iframe[\s\S]*src=\{pptPreviewUrl\}/, 'PPT preview should render deck.html inside an iframe');
assert.match(file, /window\.open\(pptExportUrl,\s*'_blank'/, 'PPT preview should expose an export action for the generated pptx');
assert.match(file, /requestFullscreen/, 'PPT preview should support fullscreen preview via Fullscreen API');
assert.match(file, /pptFullscreenActive\s*\?\s*'退出全屏'\s*:\s*'全屏预览'/, 'PPT preview should expose a fullscreen preview button');
assert.match(file, /htmlPreviewUrl|pptxUrl/, 'PPT preview should read preview and export URLs from generated file metadata');
assert.match(file, /<Button icon={<MessageOutlined \/>} onClick=\{\(\) => handleAddToChat\(viewingFile\)\}>[\s\S]*添加到对话[\s\S]*<\/Button>/, 'PPT deck preview should expose an add-to-chat action in the top button group');
assert.match(file, /file\.type === 'ppt'[\s\S]*artifactType[\s\S]*'ppt_deck'/, 'StudioPanel should write ppt_deck references when adding a PPT deck to chat');
assert.match(file, /\(viewingFile as any\)\?\.meta\?\.kind === 'ppt_outline'/, 'StudioPanel should detect PPT outline previews');
assert.match(file, /setQueuedMessage\(text\)/, 'PPT outline preview should still send a fixed generation follow-up');
assert.match(file, />\s*生成PPT\s*</, 'PPT outline preview should show a generate button');
assert.match(file, /const pptGenerationState = \(\(viewingFile\.meta as any\)\?\.generationState/, 'PPT preview should read generation state for running deck jobs');
assert.match(file, /pptKind === 'ppt_deck' && !pptPreviewUrl/, 'PPT preview should handle running deck jobs without preview HTML');
assert.match(file, /const getPptPhaseLabel = \(phase\?: string\)/, 'PPT preview should normalize generation phases into readable labels');
assert.match(file, /const PPT_PREVIEW_BASE_WIDTH = 1920;/, 'PPT preview should define a fixed base width for fit-width scaling');
assert.match(file, /const pptPreviewScale = Math\.min\(1,\s*pptPreviewFrameWidth \/ PPT_PREVIEW_BASE_WIDTH\);/, 'PPT preview should scale deck preview to fit panel width');
assert.match(file, /transform:\s*`scale\(\$\{pptPreviewScale\}\)`/, 'PPT iframe should scale down visually to fit width');
assert.match(file, /width:\s*`\$\{PPT_PREVIEW_BASE_WIDTH\}px`/, 'PPT iframe should keep a fixed internal viewport width');
assert.match(file, /height:\s*`calc\(100% \/ \$\{pptPreviewScale\}\)`/, 'PPT iframe should compensate height after scaling');
assert.match(file, /preprocessing/, 'PPT preview should map preprocessing phase explicitly');
assert.match(file, /generating_slides/, 'PPT preview should map slide generation phase explicitly');
assert.match(file, /exporting_pptx/, 'PPT preview should map export phase explicitly');
assert.doesNotMatch(
  file,
  /pptKind !== 'ppt_deck' \|\| pptPreviewUrl \|\| pptGenerationStatus !== 'running'[\s\S]*setInterval\(/,
  'StudioPanel should not auto-poll PPT progress through timers',
);
assert.doesNotMatch(file, /继续生成PPT/, 'Running PPT deck view should not queue continue-generation chat messages');
assert.doesNotMatch(file, />\s*继续生成\s*</, 'Running PPT deck view should not show a continue button');

console.log('studioPanel.ppt-preview tests passed');
