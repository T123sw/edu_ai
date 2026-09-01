import PptxGenJS from 'pptxgenjs';
import type { Action, Slide } from '@openmaic/dsl';
import { latexToOmml } from './latexToOmml.ts';

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
    } else if (
      slide.background?.type === 'image' &&
      slide.background.image?.src
    ) {
      try {
        pptxSlide.background = await resolveImageSource(
          slide.background.image.src,
        );
      } catch {
        // An unavailable optional background must not invalidate the deck.
      }
    } else if (
      slide.background?.type === 'gradient' &&
      slide.background.gradient?.colors.length
    ) {
      pptxSlide.background = {
        color: normalizeHex(
          slide.background.gradient.colors[
            slide.background.gradient.colors.length - 1
          ].color,
        ),
      };
    }

    for (const element of slide.elements ?? []) {
      try {
        if (element.type === 'text') {
          pptxSlide.addText(htmlToTextRuns(element.content, pxPerPoint), {
            x: element.left / pxPerInch,
            y: element.top / pxPerInch,
            w: element.width / pxPerInch,
            h: element.height / pxPerInch,
            rotate: element.rotate || undefined,
            fontFace: element.defaultFontName || 'Microsoft YaHei',
            fontSize: 16 / pxPerPoint,
            color: normalizeHex(element.defaultColor || '#000000'),
            fill: element.fill
              ? {
                  color: normalizeHex(element.fill),
                  transparency: opacityToTransparency(element.opacity),
                }
              : undefined,
            transparency: opacityToTransparency(element.opacity),
            margin: 0,
            valign: element.vAlign ?? 'top',
            breakLine: false,
            fit: 'shrink',
          });
          continue;
        }

        if (element.type === 'image') {
          const source = await resolveImageSource(element.src);
          pptxSlide.addImage({
            ...source,
            x: element.left / pxPerInch,
            y: element.top / pxPerInch,
            w: element.width / pxPerInch,
            h: element.height / pxPerInch,
            rotate: element.rotate || undefined,
            flipH: element.flipH,
            flipV: element.flipV,
            transparency: element.filters?.opacity
              ? 100 - Number.parseFloat(element.filters.opacity)
              : undefined,
          });
          continue;
        }

        if (element.type === 'shape') {
          const points = simpleShapePoints(
            element.path,
            element.viewBox,
            element.width,
            element.height,
            pxPerInch,
          );
          pptxSlide.addShape('custGeom' as PptxGenJS.ShapeType, {
            x: element.left / pxPerInch,
            y: element.top / pxPerInch,
            w: element.width / pxPerInch,
            h: element.height / pxPerInch,
            rotate: element.rotate || undefined,
            flipH: element.flipH,
            flipV: element.flipV,
            fill: {
              color: normalizeHex(element.fill),
              transparency: opacityToTransparency(element.opacity),
            },
            line: outlineOptions(element.outline, pxPerPoint),
            points,
          });
          if (element.text) {
            pptxSlide.addText(
              htmlToTextRuns(element.text.content, pxPerPoint),
              {
                x: element.left / pxPerInch,
                y: element.top / pxPerInch,
                w: element.width / pxPerInch,
                h: element.height / pxPerInch,
                rotate: element.rotate || undefined,
                fontFace:
                  element.text.defaultFontName || 'Microsoft YaHei',
                color: normalizeHex(element.text.defaultColor),
                fontSize: 16 / pxPerPoint,
                margin: 0,
                valign: element.text.align,
                fit: 'shrink',
              },
            );
          }
          continue;
        }

        if (element.type === 'line') {
          const [startX, startY] = element.start;
          const [endX, endY] = element.end;
          pptxSlide.addShape(pptx.ShapeType.line, {
            x: (element.left + startX) / pxPerInch,
            y: (element.top + startY) / pxPerInch,
            w: (endX - startX) / pxPerInch,
            h: (endY - startY) / pxPerInch,
            line: {
              color: normalizeHex(element.color),
              width: element.width / pxPerPoint,
              dash: lineDash(element.style),
              beginArrowType: element.points[0] === 'arrow' ? 'arrow' : 'none',
              endArrowType: element.points[1] === 'arrow' ? 'arrow' : 'none',
            },
          });
          continue;
        }

        if (element.type === 'chart') {
          const { type, barDir } = chartType(pptx, element.chartType);
          pptxSlide.addChart(
            type,
            element.data.series.map((values, index) => ({
              name: element.data.legends[index] || `Series ${index + 1}`,
              labels: element.data.labels,
              values,
            })),
            {
              x: element.left / pxPerInch,
              y: element.top / pxPerInch,
              w: element.width / pxPerInch,
              h: element.height / pxPerInch,
              rotate: element.rotate || undefined,
              barDir,
              chartColors: element.themeColors.map(normalizeHex),
              showLegend: element.data.series.length > 1,
              showTitle: false,
              showValue: false,
              catAxisLabelColor: normalizeHex(element.textColor || '#000000'),
              valAxisLabelColor: normalizeHex(element.textColor || '#000000'),
              catAxisLineColor: normalizeHex(element.lineColor || '#D1D5DB'),
              valAxisLineColor: normalizeHex(element.lineColor || '#D1D5DB'),
              showCatName: false,
            },
          );
          continue;
        }

        if (element.type === 'table') {
          pptxSlide.addTable(
            element.data.map((row) =>
              row.map((cell) => ({
                text: cell.text,
                options: {
                  bold: cell.style?.bold,
                  italic: cell.style?.em,
                  color: normalizeHex(cell.style?.color || '#000000'),
                  fill: cell.style?.backcolor
                    ? normalizeHex(cell.style.backcolor)
                    : undefined,
                  fontFace: cell.style?.fontname,
                  fontSize: cell.style?.fontsize
                    ? Number.parseFloat(cell.style.fontsize) / pxPerPoint
                    : undefined,
                  align: cell.style?.align,
                  colspan: cell.colspan,
                  rowspan: cell.rowspan,
                },
              })),
            ),
            {
              x: element.left / pxPerInch,
              y: element.top / pxPerInch,
              w: element.width / pxPerInch,
              h: element.height / pxPerInch,
              colW: element.colWidths.map(
                (ratio) => (ratio * element.width) / pxPerInch,
              ),
              rowH: (element.rowHeights ?? []).map(
                (height) => height / pxPerInch,
              ),
              border: {
                type: lineDash(element.outline.style),
                color: normalizeHex(element.outline.color || '#000000'),
                pt: (element.outline.width || 1) / pxPerPoint,
              },
              margin: 0.04,
              fontFace: slide.theme.fontName || 'Microsoft YaHei',
              fontSize: 14 / pxPerPoint,
            },
          );
          continue;
        }

        if (element.type === 'latex') {
          const lineCount = (element.latex.match(/\\\\/g) ?? []).length + 1;
          const boxHeightPoints = element.height / pxPerPoint;
          const fontSize = Math.max(
            8,
            Math.round(boxHeightPoints / (lineCount * 3)),
          );
          const omml = latexToOmml(element.latex, fontSize);
          if (omml) {
            pptxSlide.addFormula({
              omml,
              x: element.left / pxPerInch,
              y: element.top / pxPerInch,
              w: element.width / pxPerInch,
              h: element.height / pxPerInch,
              fontSize,
              color: normalizeHex(element.color || '#000000'),
              align: element.align ?? 'center',
            });
          } else if (element.path && element.viewBox) {
            const svg = formulaSvg(
              element.path,
              element.viewBox,
              element.color || '#000000',
              element.strokeWidth || 1,
            );
            pptxSlide.addImage({
              data: svg,
              x: element.left / pxPerInch,
              y: element.top / pxPerInch,
              w: element.width / pxPerInch,
              h: element.height / pxPerInch,
            });
          }
          continue;
        }

        if (element.type === 'video' || element.type === 'audio') {
          let poster: string | undefined;
          if (element.type === 'video' && element.poster) {
            try {
              const posterSource = await resolveImageSource(element.poster);
              poster = 'data' in posterSource
                ? posterSource.data
                : posterSource.path;
            } catch {
              poster = undefined;
            }
          }

          let embedded = false;
          if (element.src) {
            try {
              const media = await resolveMediaSource(
                element.src,
                element.ext,
                element.type,
              );
              pptxSlide.addMedia({
                ...media,
                type: element.type,
                x: element.left / pxPerInch,
                y: element.top / pxPerInch,
                w: element.width / pxPerInch,
                h: element.height / pxPerInch,
                cover: poster,
              });
              embedded = true;
            } catch {
              embedded = false;
            }
          }

          if (!embedded && element.type === 'video' && poster) {
            pptxSlide.addImage({
              data: poster,
              x: element.left / pxPerInch,
              y: element.top / pxPerInch,
              w: element.width / pxPerInch,
              h: element.height / pxPerInch,
            });
          }
        }
      } catch {
        // Unsupported or unavailable individual elements degrade by omission.
      }
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

function opacityToTransparency(opacity?: number): number | undefined {
  if (opacity === undefined) return undefined;
  return Math.round((1 - Math.min(1, Math.max(0, opacity))) * 100);
}

function outlineOptions(
  outline: { style?: string; width?: number; color?: string } | undefined,
  pxPerPoint: number,
): PptxGenJS.ShapeLineProps | undefined {
  if (!outline?.width) return undefined;
  return {
    color: normalizeHex(outline.color || '#000000'),
    width: outline.width / pxPerPoint,
    dash: lineDash(outline.style),
  };
}

function lineDash(
  style?: string,
): 'solid' | 'dash' | 'sysDot' {
  if (style === 'dashed') return 'dash';
  if (style === 'dotted') return 'sysDot';
  return 'solid';
}

function chartType(
  pptx: PptxGenJS,
  type: string,
): { type: PptxGenJS.ChartType; barDir?: 'bar' | 'col' } {
  if (type === 'bar') return { type: pptx.ChartType.bar, barDir: 'bar' };
  if (type === 'column') return { type: pptx.ChartType.bar, barDir: 'col' };
  if (type === 'pie') return { type: pptx.ChartType.pie };
  if (type === 'ring') return { type: pptx.ChartType.doughnut };
  if (type === 'area') return { type: pptx.ChartType.area };
  if (type === 'radar') return { type: pptx.ChartType.radar };
  if (type === 'scatter') return { type: pptx.ChartType.scatter };
  return { type: pptx.ChartType.line };
}

function simpleShapePoints(
  path: string,
  viewBox: [number, number],
  width: number,
  height: number,
  pxPerInch: number,
): NonNullable<PptxGenJS.ShapeProps['points']> {
  const tokens =
    path.match(/[MLHVZmlhvz]|-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/g) ?? [];
  const points: NonNullable<PptxGenJS.ShapeProps['points']> = [];
  const scaleX = width / viewBox[0] / pxPerInch;
  const scaleY = height / viewBox[1] / pxPerInch;
  let command = '';
  let cursorX = 0;
  let cursorY = 0;
  let index = 0;

  while (index < tokens.length) {
    if (/^[a-z]$/i.test(tokens[index])) {
      command = tokens[index++];
      if (command.toUpperCase() === 'Z') {
        points.push({ close: true });
        continue;
      }
    }
    const relative = command === command.toLowerCase();
    const upper = command.toUpperCase();
    if (upper === 'M' || upper === 'L') {
      if (index + 1 >= tokens.length) break;
      const nextX = Number(tokens[index++]);
      const nextY = Number(tokens[index++]);
      cursorX = relative ? cursorX + nextX : nextX;
      cursorY = relative ? cursorY + nextY : nextY;
      points.push({
        x: cursorX * scaleX,
        y: cursorY * scaleY,
        moveTo: upper === 'M',
      });
      if (upper === 'M') command = relative ? 'l' : 'L';
      continue;
    }
    if (upper === 'H') {
      const nextX = Number(tokens[index++]);
      cursorX = relative ? cursorX + nextX : nextX;
      points.push({ x: cursorX * scaleX, y: cursorY * scaleY });
      continue;
    }
    if (upper === 'V') {
      const nextY = Number(tokens[index++]);
      cursorY = relative ? cursorY + nextY : nextY;
      points.push({ x: cursorX * scaleX, y: cursorY * scaleY });
      continue;
    }
    throw new Error(`Unsupported basic shape path command: ${command}`);
  }

  if (points.length < 2) throw new Error('Shape path contains too few points');
  return points;
}

async function resolveImageSource(
  source: string,
): Promise<{ data: string } | { path: string }> {
  if (/^data:image\//i.test(source)) return { data: source };
  if (!/^(?:https?:|blob:)/i.test(source)) return { path: source };

  const response = await fetch(source);
  if (!response.ok) {
    throw new Error(`Unable to embed image (${response.status}): ${source}`);
  }
  const contentType =
    response.headers.get('content-type')?.split(';')[0] || 'image/png';
  const bytes = new Uint8Array(await response.arrayBuffer());
  return {
    data: `data:${contentType};base64,${bytesToBase64(bytes)}`,
  };
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

async function resolveMediaSource(
  source: string,
  extension: string | undefined,
  type: 'video' | 'audio',
): Promise<
  ({ data: string } | { path: string }) & { extn: string }
> {
  const dataMatch = source.match(/^data:([^;,]+);base64,/i);
  if (dataMatch) {
    return {
      data: source,
      extn: normalizeMediaExtension(
        extension || extensionFromMime(dataMatch[1], type),
      ),
    };
  }
  if (!/^(?:https?:|blob:)/i.test(source)) {
    return {
      path: source,
      extn: normalizeMediaExtension(
        extension || extensionFromPath(source) || defaultMediaExtension(type),
      ),
    };
  }

  const response = await fetch(source);
  if (!response.ok) {
    throw new Error(`Unable to embed media (${response.status}): ${source}`);
  }
  const mime =
    response.headers.get('content-type')?.split(';')[0] ||
    (type === 'video' ? 'video/mp4' : 'audio/mpeg');
  const bytes = new Uint8Array(await response.arrayBuffer());
  return {
    data: `data:${mime};base64,${bytesToBase64(bytes)}`,
    extn: normalizeMediaExtension(
      extension ||
        extensionFromPath(source) ||
        extensionFromMime(mime, type),
    ),
  };
}

function extensionFromMime(
  mime: string,
  type: 'video' | 'audio',
): string {
  const subtype = mime.split('/')[1]?.toLowerCase();
  if (subtype === 'mpeg') return type === 'video' ? 'mpeg' : 'mp3';
  if (subtype === 'x-m4a') return 'm4a';
  if (subtype === 'quicktime') return 'mov';
  return subtype || defaultMediaExtension(type);
}

function extensionFromPath(path: string): string | undefined {
  return path.match(/\.([a-z0-9]+)(?:[?#]|$)/i)?.[1];
}

function defaultMediaExtension(type: 'video' | 'audio'): string {
  return type === 'video' ? 'mp4' : 'mp3';
}

function normalizeMediaExtension(extension: string): string {
  return extension.replace(/^\./, '').toLowerCase();
}

function formulaSvg(
  path: string,
  viewBox: [number, number],
  color: string,
  strokeWidth: number,
): string {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" ' +
    `viewBox="0 0 ${viewBox[0]} ${viewBox[1]}" ` +
    `fill="none" stroke="${escapeXml(color)}" ` +
    `stroke-width="${strokeWidth}" stroke-linecap="round" ` +
    'stroke-linejoin="round">' +
    `<path d="${escapeXml(path)}"/></svg>`;
  return `data:image/svg+xml;base64,${bytesToBase64(
    new TextEncoder().encode(svg),
  )}`;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

interface InlineTextStyle {
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
  color?: string;
  fontFace?: string;
  fontSize?: number;
}

function htmlToTextRuns(
  html: string,
  pxPerPoint: number,
): PptxGenJS.TextProps[] {
  const runs: PptxGenJS.TextProps[] = [];
  const stack: Array<{ tag: string; style: InlineTextStyle }> = [
    { tag: 'root', style: {} },
  ];
  const tokens = html.match(/<[^>]+>|[^<]+/g) ?? [];

  for (const token of tokens) {
    if (!token.startsWith('<')) {
      const text = decodeHtml(token).replace(/\r?\n/g, '');
      if (!text) continue;
      const style = stack[stack.length - 1].style;
      runs.push({
        text,
        options: {
          bold: style.bold,
          italic: style.italic,
          underline: style.underline ? { style: 'sng' } : undefined,
          strike: style.strike ? 'sngStrike' : undefined,
          color: style.color ? normalizeHex(style.color) : undefined,
          fontFace: style.fontFace,
          fontSize: style.fontSize
            ? style.fontSize / pxPerPoint
            : undefined,
        },
      });
      continue;
    }

    const tagMatch = token.match(/^<\/?\s*([a-z0-9]+)/i);
    if (!tagMatch) continue;
    const tag = tagMatch[1].toLowerCase();
    const closing = /^<\//.test(token);
    if (closing) {
      if (['p', 'div', 'li'].includes(tag) && runs.length) {
        runs[runs.length - 1].options = {
          ...runs[runs.length - 1].options,
          breakLine: true,
        };
      }
      const matchIndex = stack.map((entry) => entry.tag).lastIndexOf(tag);
      if (matchIndex > 0) stack.splice(matchIndex);
      continue;
    }
    if (tag === 'br') {
      runs.push({ text: '', options: { breakLine: true } });
      continue;
    }

    const style = { ...stack[stack.length - 1].style };
    if (tag === 'strong' || tag === 'b') style.bold = true;
    if (tag === 'em' || tag === 'i') style.italic = true;
    if (tag === 'u') style.underline = true;
    if (tag === 's' || tag === 'strike') style.strike = true;
    applyInlineStyle(token, style);
    stack.push({ tag, style });
  }

  if (runs.at(-1)?.options?.breakLine) {
    runs.at(-1)!.options!.breakLine = false;
  }
  return runs.length
    ? runs
    : [{ text: htmlToPlainText(html), options: {} }];
}

function applyInlineStyle(token: string, style: InlineTextStyle): void {
  const styleMatch = token.match(/\sstyle\s*=\s*["']([^"']+)["']/i);
  if (!styleMatch) return;
  for (const declaration of styleMatch[1].split(';')) {
    const [rawKey, rawValue] = declaration.split(':', 2);
    const key = rawKey?.trim().toLowerCase();
    const value = rawValue?.trim();
    if (!key || !value) continue;
    if (key === 'font-weight' && (value === 'bold' || Number(value) >= 600)) {
      style.bold = true;
    } else if (key === 'font-style' && value === 'italic') {
      style.italic = true;
    } else if (key === 'text-decoration') {
      style.underline = value.includes('underline');
      style.strike = value.includes('line-through');
    } else if (key === 'color') {
      style.color = value;
    } else if (key === 'font-family') {
      style.fontFace = value.replace(/^["']|["']$/g, '');
    } else if (key === 'font-size') {
      style.fontSize = Number.parseFloat(value);
    }
  }
}

function decodeHtml(text: string): string {
  return text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&amp;/gi, '&');
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
