import assert from 'node:assert/strict';
import test from 'node:test';
import {sharedQuestionStem} from './questionPresentation';

test('removes duplicated children while keeping shared conditions and code intact', () => {
  const children = [{question: '补全代码：\n\n```c\na) sample();\n```'}, {question: '给出最坏情况复杂度。'}];
  const shared = '## 链表\n\n假设头结点非空，以下两问使用同一链表。';
  assert.equal(sharedQuestionStem(`${shared}\n\n**a)** ${children[0].question}\n\n**b)** ${children[1].question}`, children), shared);
});

test('keeps additional conditions or merely similar parent text', () => {
  const question = '已知数组。\n\na) 求比较次数。\n\n注意：只统计关键字比较。\n\nb) 求最坏时间复杂度。';
  assert.equal(sharedQuestionStem(question, [{question: '求比较次数。'}, {question: '求时间复杂度。'}]), question);
});

test('supports numeric and parenthesized labels and CRLF without changing child content', () => {
  const children = [{question: '计算 $n+1$。'}, {question: '```\r\na) code\r\n```'}];
  assert.equal(sharedQuestionStem(`公共条件\r\n\r\n(1) ${children[0].question}\r\n\r\n2. ${children[1].question}`, children), '公共条件');
  assert.equal(children[1].question, '```\r\na) code\r\n```');
});

test('does not treat labels in fenced code as duplicate question blocks', () => {
  const question = '公共代码\n~~~~text\na) 示例\n~~~\nb) 示例2\n~~~~\n尾注';
  assert.equal(sharedQuestionStem(question, [{question: '示例'}, {question: '示例2'}]), question);
});

test('retains options and unmatched blocks instead of dropping unique content', () => {
  const question = 'a) 选择结构。\nA. 单链表\nB. 双链表\n\nb) 计算长度。';
  assert.equal(sharedQuestionStem(question, [{question: '选择结构。'}, {question: '计算长度。'}]), 'a) 选择结构。\nA. 单链表\nB. 双链表');
});

test('leaves standalone questions untouched and permits an empty shared stem', () => {
  assert.equal(sharedQuestionStem('  普通题。\n', []), '  普通题。\n');
  assert.equal(sharedQuestionStem('a) 计算长度。', [{question: '计算长度。'}]), '');
  assert.equal(sharedQuestionStem('b) 计算长度。', [{question: '计算长度。'}]), 'b) 计算长度。');
});
