export type SourceHighlightRange = {
  start: number;
  end: number;
};

export function stripRetrievalContextPrefix(source: string): string {
  return String(source || '')
    .replace(/\r\n?/g, '\n')
    .replace(/^【章节上下文】\s*[:：]\s*[^\n]*\n+/, '')
    .trim();
}

function normalizeWithSourceMap(source: string): {
  text: string;
  starts: number[];
  ends: number[];
} {
  const characters: string[] = [];
  const starts: number[] = [];
  const ends: number[] = [];
  let whitespaceStart = -1;

  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (/\s/.test(character)) {
      if (characters.length > 0 && whitespaceStart === -1) {
        whitespaceStart = index;
      }
      continue;
    }

    if (whitespaceStart !== -1 && characters.length > 0) {
      characters.push(' ');
      starts.push(whitespaceStart);
      ends.push(index);
      whitespaceStart = -1;
    }
    characters.push(character);
    starts.push(index);
    ends.push(index + 1);
  }

  return { text: characters.join(''), starts, ends };
}

export function locateSourceHighlightRange(
  fullText: string,
  rawSourceText: string,
): SourceHighlightRange | null {
  const sourceText = stripRetrievalContextPrefix(rawSourceText);
  if (!fullText || !sourceText) return null;

  const exactStart = fullText.indexOf(sourceText);
  if (exactStart >= 0) {
    return { start: exactStart, end: exactStart + sourceText.length };
  }

  const normalizedFull = normalizeWithSourceMap(fullText);
  const normalizedSource = normalizeWithSourceMap(sourceText).text;
  if (!normalizedSource) return null;

  const normalizedStart = normalizedFull.text.indexOf(normalizedSource);
  if (normalizedStart < 0) return null;

  const normalizedEnd = normalizedStart + normalizedSource.length - 1;
  const start = normalizedFull.starts[normalizedStart];
  const end = normalizedFull.ends[normalizedEnd];
  if (start === undefined || end === undefined || end <= start) return null;

  return { start, end };
}
