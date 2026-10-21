import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeQuizMarkdown } from './quizPresentation';

test('prose math and HTML normalize without altering fenced or inline source code', () => {
  const code = '```cpp\nif (x < y) {\n    print("<br> \\(literal\\)");\n}\n\n\n\n```';
  const output = normalizeQuizMarkdown('公式 \\(n^2\\) <br>下一行\n\n'+code+'\n\n字面量 `<br>`');
  assert.ok(output.includes('公式 $n^2$ \n下一行'));
  assert.ok(output.includes(code));
  assert.ok(output.endsWith('字面量 `<br>`'));
});
test('unlabelled, tilde and unfinished code fences preserve indentation and symbols', () => {
  for (const source of ['```\nfunction f() {\n    return x < y;\n}\n```', '~~~text\n\\(x\\) <br>\n~~~', '```\n    <sup>literal</sup>']) assert.equal(normalizeQuizMarkdown(source), source);
});
