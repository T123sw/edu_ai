import PptxGenJS from 'pptxgenjs';
import type { Action, Slide } from '@openmaic/dsl';

export interface PptxExportScene {
  id: string;
  order?: number;
  type: string;
  content?: {
    type?: string;
    canvas?: Slide;
  };
  actions?: Action[];
}

export interface ClassroomPptxInput {
  title: string;
  scenes: readonly PptxExportScene[];
}

interface SlideScene {
  scene: PptxExportScene;
  slide: Slide;
  sourceIndex: number;
}

export async function buildClassroomPptx(
  input: ClassroomPptxInput,
): Promise<Blob> {
  const slideScenes = input.scenes
    .map((scene, sourceIndex) => ({ scene, sourceIndex }))
    .filter(
      (
        entry,
      ): entry is {
        scene: PptxExportScene & { content: { type?: string; canvas: Slide } };
        sourceIndex: number;
      } =>
        entry.scene.content?.type === 'slide' &&
        entry.scene.content.canvas !== undefined,
    )
    .map<SlideScene>(({ scene, sourceIndex }) => ({
      scene,
      slide: scene.content.canvas,
      sourceIndex,
    }))
    .sort(
      (left, right) =>
        (left.scene.order ?? left.sourceIndex) -
          (right.scene.order ?? right.sourceIndex) ||
        left.sourceIndex - right.sourceIndex,
    );

  if (slideScenes.length === 0) {
    throw new Error('PPTX export requires at least one slide scene');
  }

  const pptx = new PptxGenJS();
  pptx.author = 'edu_ai';
  pptx.company = 'edu_ai';
  pptx.subject = 'OpenMAIC classroom export';
  pptx.title = input.title;
  pptx.layout = layoutForRatio(slideScenes[0].slide.viewportRatio);

  for (const { scene, slide } of slideScenes) {
    const pptxSlide = pptx.addSlide();
    const pxPerInch = slide.viewportSize / 10;
    const pxPerPoint = slide.viewportSize / 720;

    if (slide.background?.type === 'solid' && slide.background.color) {
      pptxSlide.background = {
        color: normalizeHex(slide.background.color),
      };
    }

    for (const element of slide.elements ?? []) {
      if (element.type !== 'text') continue;
      pptxSlide.addText(htmlToPlainText(element.content), {
        x: element.left / pxPerInch,
        y: element.top / pxPerInch,
        w: element.width / pxPerInch,
        h: element.height / pxPerInch,
        rotate: element.rotate || undefined,
        fontFace: element.defaultFontName || 'Microsoft YaHei',
        fontSize: 16 / pxPerPoint,
        color: normalizeHex(element.defaultColor || '#000000'),
        margin: 0,
        valign: 'top',
        breakLine: false,
        fit: 'shrink',
      });
    }

    const notes = (scene.actions ?? [])
      .filter(
        (action): action is Extract<Action, { type: 'speech' }> =>
          action.type === 'speech',
      )
      .map((action) => action.text)
      .filter(Boolean)
      .join('\n');
    if (notes) pptxSlide.addNotes(notes);
  }

  return (await pptx.write({
    outputType: 'blob',
    compression: true,
  })) as Blob;
}

function layoutForRatio(ratio: number): string {
  if (Math.abs(ratio - 0.75) < 0.01) return 'LAYOUT_4x3';
  if (Math.abs(ratio - 0.625) < 0.01) return 'LAYOUT_16x10';
  return 'LAYOUT_16x9';
}

function normalizeHex(color: string): string {
  const match = color.trim().match(/^#?([\da-f]{6})$/i);
  return match?.[1].toUpperCase() ?? '000000';
}

function htmlToPlainText(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(?:p|div|li)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
