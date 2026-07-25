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

const ONE_PIXEL_PNG =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

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

test('preserves background, element geometry, image data, and z-order', async () => {
  const canvas = slide('visual-slide', 'unused');
  canvas.background = { type: 'solid', color: '#112233' };
  canvas.elements = [
    {
      id: 'bottom-text',
      type: 'text',
      left: 100,
      top: 200,
      width: 800,
      height: 100,
      rotate: 15,
      content: '<p>FIRST_LAYER</p>',
      defaultFontName: 'Noto Sans SC',
      defaultColor: '#445566',
      fill: '#DDEEFF',
      opacity: 0.75,
      vAlign: 'middle',
    },
    {
      id: 'middle-image',
      type: 'image',
      left: 200,
      top: 300,
      width: 400,
      height: 200,
      rotate: 0,
      fixedRatio: false,
      src: ONE_PIXEL_PNG,
    },
    {
      id: 'top-text',
      type: 'text',
      left: 300,
      top: 400,
      width: 500,
      height: 100,
      rotate: 0,
      content: '<p>TOP_LAYER</p>',
      defaultFontName: 'Microsoft YaHei',
      defaultColor: '#778899',
    },
  ];

  const zip = await unzip(
    await buildClassroomPptx({
      title: 'visual-fidelity',
      scenes: [scene('scene-visual', 1, canvas)],
    }),
  );
  const xml = await zip.file('ppt/slides/slide1.xml')!.async('string');

  assert.match(xml, /<p:bg>[\s\S]*?<a:srgbClr val="112233"/);
  assert.match(
    xml,
    /<a:off x="914400" y="1828800"\/><a:ext cx="7315200" cy="914400"\/>/,
  );
  assert.match(xml, /rot="900000"/);
  assert.match(xml, /typeface="Noto Sans SC"/);
  assert.match(xml, /<a:srgbClr val="445566"/);
  assert.equal(
    Object.keys(zip.files).filter((name) => /^ppt\/media\/.+\.png$/.test(name))
      .length,
    1,
  );

  const bottomIndex = xml.indexOf('FIRST_LAYER');
  const imageIndex = xml.indexOf('<p:pic>');
  const topIndex = xml.indexOf('TOP_LAYER');
  assert.ok(bottomIndex >= 0 && bottomIndex < imageIndex);
  assert.ok(imageIndex < topIndex);
});

test('exports styled text, basic shapes, lines, charts, and tables', async () => {
  const canvas = slide('component-slide', 'unused');
  canvas.elements = [
    {
      id: 'styled-text',
      type: 'text',
      left: 40,
      top: 30,
      width: 500,
      height: 80,
      rotate: 0,
      content: '<p><strong>BOLD_TEXT</strong> plain</p>',
      defaultFontName: 'Microsoft YaHei',
      defaultColor: '#111111',
    },
    {
      id: 'basic-shape',
      type: 'shape',
      left: 50,
      top: 140,
      width: 200,
      height: 120,
      rotate: 0,
      viewBox: [200, 120],
      path: 'M 0 0 L 200 0 L 200 120 L 0 120 Z',
      fixedRatio: false,
      fill: '#22C55E',
      outline: { color: '#14532D', width: 2, style: 'solid' },
      text: {
        content: '<p>SHAPE_TEXT</p>',
        defaultFontName: 'Microsoft YaHei',
        defaultColor: '#FFFFFF',
        align: 'middle',
      },
    },
    {
      id: 'basic-line',
      type: 'line',
      left: 0,
      top: 0,
      width: 3,
      start: [100, 300],
      end: [800, 300],
      style: 'dashed',
      color: '#DC2626',
      points: ['', 'arrow'],
    },
    {
      id: 'basic-chart',
      type: 'chart',
      left: 300,
      top: 140,
      width: 300,
      height: 250,
      rotate: 0,
      chartType: 'column',
      data: {
        labels: ['A', 'B'],
        legends: ['Score'],
        series: [[3, 7]],
      },
      themeColors: ['#2563EB'],
      textColor: '#111827',
      lineColor: '#CBD5E1',
    },
    {
      id: 'basic-table',
      type: 'table',
      left: 100,
      top: 450,
      width: 800,
      height: 160,
      rotate: 0,
      outline: { color: '#334155', width: 1, style: 'solid' },
      colWidths: [0.5, 0.5],
      cellMinHeight: 40,
      data: [
        [
          { id: 'a', colspan: 1, rowspan: 1, text: 'TABLE_A' },
          { id: 'b', colspan: 1, rowspan: 1, text: 'TABLE_B' },
        ],
      ],
    },
  ];

  const zip = await unzip(
    await buildClassroomPptx({
      title: 'component-fidelity',
      scenes: [scene('scene-components', 1, canvas)],
    }),
  );
  const xml = await zip.file('ppt/slides/slide1.xml')!.async('string');

  assert.match(xml, /<a:rPr[^>]*b="1"/);
  assert.match(xml, /SHAPE_TEXT/);
  assert.match(xml, /val="22C55E"/);
  assert.match(xml, /val="DC2626"/);
  assert.match(xml, /TABLE_A/);
  assert.match(xml, /TABLE_B/);
  assert.ok(zip.file('ppt/charts/chart1.xml'));
});

test('embeds an image background and omits unsupported elements safely', async () => {
  const canvas = slide('background-slide', 'AFTER_UNSUPPORTED');
  canvas.background = {
    type: 'image',
    image: { src: ONE_PIXEL_PNG, size: 'cover' },
  };
  canvas.elements.unshift({
    id: 'unsupported-code',
    type: 'code',
    left: 0,
    top: 0,
    width: 100,
    height: 100,
    rotate: 0,
    language: 'typescript',
    lines: [{ id: 'L1', content: 'const ignored = true;' }],
  });

  const zip = await unzip(
    await buildClassroomPptx({
      title: 'background-image',
      scenes: [scene('scene-background', 1, canvas)],
    }),
  );
  const xml = await zip.file('ppt/slides/slide1.xml')!.async('string');

  assert.match(xml, /<p:bg>[\s\S]*?<a:blip r:embed="rId\d+"/);
  assert.match(xml, /AFTER_UNSUPPORTED/);
  assert.equal(
    Object.keys(zip.files).filter((name) => /^ppt\/media\/.+\.png$/.test(name))
      .length,
    1,
  );
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
