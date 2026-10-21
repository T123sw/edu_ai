import { normalizeKnowledgeMarkdown } from '../stitch/components/knowledgeMarkdown';

export function normalizeQuizMarkdown(source: string): string {
  // Imported prose normalization must never rewrite literal code (HTML, LaTeX or blank lines).
  let prefix = 'QUIZCODEPLACEHOLDER';
  while (source.includes(prefix)) prefix += 'X';
  const protectedCode: string[] = [];
  const save = (value: string) => `${prefix}${protectedCode.push(value) - 1}END`;
  let fence: { marker: string; length: number } | undefined;
  let block: string[] = [];
  const lines: string[] = [];
  for (const line of source.replace(/\r\n?/g, '\n').split('\n')) {
    if (fence) {
      block.push(line);
      const end = line.match(/^ {0,3}(`+|~+)\s*$/);
      if (end && end[1][0] === fence.marker && end[1].length >= fence.length) {
        lines.push(save(block.join('\n'))); block = []; fence = undefined;
      }
    } else {
      const start = line.match(/^ {0,3}(`{3,}|~{3,})/);
      if (start) { fence = { marker: start[1][0], length: start[1].length }; block = [line]; }
      else lines.push(line.replace(/(`+)([^`]*?)\1/g, save));
    }
  }
  if (block.length) lines.push(save(block.join('\n')));
  return normalizeKnowledgeMarkdown(lines.join('\n')).replace(new RegExp(`${prefix}(\\d+)END`, 'g'), (_, index: string) => protectedCode[Number(index)]);
}

export function quizTypeLabel(type?: string) {
  return type === 'single_choice' ? '单选题' : type === 'multiple_choice' ? '多选题' : type === 'true_false' ? '判断题' : type === 'short_answer' ? '简答题' : '练习';
}
