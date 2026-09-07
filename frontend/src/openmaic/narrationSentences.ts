export function narrationSentences(text: string): string[] {
  return (text.match(/[^。！？!?\n]+[。！？!?]*(?:[”’」』])?|[^\n]+/g) || []).map((part) => part.trim()).filter(Boolean);
}

export function sentenceAtProgress(text: string, progress: number): string {
  const sentences = narrationSentences(text);
  const total = sentences.reduce((sum, sentence) => sum + sentence.length, 0);
  const position = Math.max(0, Math.min(0.999999, progress)) * total;
  let end = 0;
  return sentences.find((sentence) => { end += sentence.length; return position < end; }) || "";
}
