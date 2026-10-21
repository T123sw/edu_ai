type Child = {question: string};

// Remove only whole, explicitly numbered blocks identical to a structured child.
// Extra conditions, different wording and anything inside code fences stay intact.
export function sharedQuestionStem(question: string, children: readonly Child[]): string {
  if (!children.length) return question;
  const source = question.replace(/\r\n/g, '\n');
  const blocks: {start: number; body: number; child: number}[] = [];
  let offset = 0;
  let fence: {char: string; length: number} | undefined;
  for (const line of source.split('\n')) {
    const code = /^ {0,3}(`{3,}|~{3,})/.exec(line);
    if (fence) {
      if (code && code[1][0] === fence.char && code[1].length >= fence.length && !line.slice(code[0].length).trim()) fence = undefined;
    } else if (code) {
      fence = {char: code[1][0], length: code[1].length};
    } else {
      const label = /^ {0,3}(?:#{1,6}[ \t]+)?(?:\*\*)?(?:\(([a-z]|\d+)\)|（([a-z]|\d+)）|([a-z]|\d+)[.)、])(?:\*\*)?[ \t]+/.exec(line);
      if (label) {
        const value = label[1] || label[2] || label[3];
        const child = /^\d+$/.test(value) ? Number(value) - 1 : value.charCodeAt(0) - 97;
        blocks.push({start: offset, body: offset + label[0].length, child});
        const childCode = /^(`{3,}|~{3,})/.exec(line.slice(label[0].length));
        if (childCode) fence = {char: childCode[1][0], length: childCode[1].length};
      }
    }
    offset += line.length + 1;
  }
  let stem = source;
  for (let index = blocks.length - 1; index >= 0; index--) {
    const block = blocks[index], end = blocks[index + 1]?.start ?? source.length;
    const child = children[block.child]?.question.replace(/\r\n/g, '\n').trim();
    if (child && source.slice(block.body, end).trim() === child) {
      stem = stem.slice(0, block.start) + stem.slice(end);
    }
  }
  return stem.trim();
}
