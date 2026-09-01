import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import {
  buildResourceQaSessionPath,
  buildResourceQaTurnsPath,
  submitResourceQaTurn,
} from "./resourceQa.ts";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;

afterEach(() => {
  globalThis.fetch = originalFetch;
  Object.defineProperty(globalThis, "window", { configurable: true, value: originalWindow });
});

test("resource QA paths encode every resource identity", () => {
  assert.equal(
    buildResourceQaSessionPath("course / 一", "study_guide", "guide?#", 2),
    "/api/courses/course%20%2F%20%E4%B8%80/resources/study_guide/guide%3F%23/qa/session?resource_version=2",
  );
  assert.equal(
    buildResourceQaTurnsPath("course / 一", "practice", "quiz?#"),
    "/api/courses/course%20%2F%20%E4%B8%80/resources/practice/quiz%3F%23/qa/turns",
  );
});

test("resource turn always sends the exact version, full scope, and anchor", async () => {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { localStorage: { getItem: () => null } },
  });
  let body: Record<string, unknown> = {};
  globalThis.fetch = async (_input, init) => {
    body = JSON.parse(String(init?.body));
    return new Response(JSON.stringify({ session_id: "s", turn: {} }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  await submitResourceQaTurn("course-1", "practice", "quiz-1", {
    client_turn_id: "client-1",
    question: "为什么？",
    resource_version: 3,
    context_scope: "full_resource",
    anchor: { question_id: "q-2" },
  });

  assert.equal(body.resource_version, 3);
  assert.equal(body.context_scope, "full_resource");
  assert.deepEqual(body.anchor, { question_id: "q-2" });
});
