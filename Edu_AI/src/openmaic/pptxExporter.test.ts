import assert from 'node:assert/strict';
import { test } from 'node:test';
import JSZip from 'jszip';
import type { Slide } from '@openmaic/dsl';
import {
  buildClassroomPptx,
  type PptxExportScene,
} from './pptxExporter.ts';

function slide(id: string, text: string): Slide {
  return {
    id,
    viewportSize: 1000,
    viewportRatio: 0.5625,
    theme: {
      backgroundColor: '#ffffff',
      themeColors: ['#2563eb'],
      fontColor: '#111827',
      fontName: 'Microsoft YaHei',
    },
    background: { type: 'solid', color: '#ffffff' },
    elements: [
      {
        id: `${id}-text`,
        type: 'text',
        left: 100,
        top: 100,
        width: 800,
        height: 120,
        rotate: 0,
        content: `<p>${text}</p>`,
        defaultFontName: 'Microsoft YaHei',
        defaultColor: '#111827',
      },
    ],
  };
}

function scene(
  id: string,
  order: number,
  canvas: Slide,
  speechText?: string,
): PptxExportScene {
  return {
    id,
    order,
    type: 'slide',
    content: { type: 'slide', canvas },
    actions: speechText
      ? [{ id: `${id}-speech`, type: 'speech', text: speechText }]
      : [],
  };
}

async function unzip(blob: Blob): Promise<JSZip> {
  return JSZip.loadAsync(await blob.arrayBuffer());
}

test('builds a valid PPTX ZIP and filters non-slide scenes', async () => {
  const blob = await buildClassroomPptx({
    title: '算法课程',
    scenes: [
      scene('scene-1', 1, slide('slide-1', '第一页')),
      {
        id: 'interactive-1',
        order: 2,
        type: 'interactive',
        content: { type: 'interactive' },
        actions: [],
      },
    ],
  });
  const zip = await unzip(blob);

  assert.ok(blob.size > 5000);
  assert.ok(zip.file('[Content_Types].xml'));
  assert.ok(zip.file('ppt/slides/slide1.xml'));
  assert.equal(zip.file('ppt/slides/slide2.xml'), null);
});

test('sorts slide scenes by order without mutating the source', async () => {
  const scenes = [
    scene('scene-2', 2, slide('slide-2', '第二页')),
    scene('scene-1', 1, slide('slide-1', '第一页')),
  ];
  const before = structuredClone(scenes);
  const zip = await unzip(
    await buildClassroomPptx({ title: '排序测试', scenes }),
  );
  const firstSlideXml = await zip
    .file('ppt/slides/slide1.xml')!
    .async('string');
  const secondSlideXml = await zip
    .file('ppt/slides/slide2.xml')!
    .async('string');

  assert.match(firstSlideXml, /第一页/);
  assert.match(secondSlideXml, /第二页/);
  assert.deepEqual(scenes, before);
});

test('writes speech actions into speaker notes', async () => {
  const zip = await unzip(
    await buildClassroomPptx({
      title: '讲稿测试',
      scenes: [
        scene(
          'scene-notes',
          1,
          slide('slide-notes', '正文'),
          '这是演讲者备注。',
        ),
      ],
    }),
  );
  const notesXml = await zip
    .file('ppt/notesSlides/notesSlide1.xml')!
    .async('string');

  assert.match(notesXml, /这是演讲者备注。/);
});
