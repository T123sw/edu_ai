import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


const source = readFileSync(
  new URL("./ClassroomSceneRenderer.tsx", import.meta.url),
  "utf8",
);


test("resource quiz scenes forward answer submissions to the learning recorder", () => {
  const quizBranch = source.match(/case 'quiz':([\s\S]*?)case 'invalid':/)?.[1] ?? "";

  assert.match(quizBranch, /onSubmitAnswers=\{onQuizSubmitAnswers\}/);
});

test("interactive scenes forward demo actions to the learning recorder", () => {
  const interactiveBranch = source.match(
    /case 'interactive':([\s\S]*?)case 'quiz':/,
  )?.[1] ?? "";

  assert.match(interactiveBranch, /onInteraction=\{onDemoInteraction\}/);
});
