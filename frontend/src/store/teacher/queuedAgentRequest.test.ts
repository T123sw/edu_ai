import assert from "node:assert/strict";
import test from "node:test";

const values = new Map<string, string>();
Object.defineProperty(globalThis, "window", {
  configurable: true,
  value: {
    localStorage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    },
  },
});

let useStore: typeof import("./useStore").useStore;

test.before(async () => {
  ({ useStore } = await import("./useStore.ts"));
});

const first = {
  requestId: "request-1",
  text: "生成报告",
  resourceType: "report" as const,
  actionHint: "generate.report" as const,
  ownerUserId: "teacher-a",
  courseId: "course-a",
  scopeType: "course" as const,
  sourceMode: "none" as const,
  selectedDocumentIds: [] as string[],
  allowRag: false,
  allowWeb: false,
};

test.beforeEach(() => {
  useStore.setState({ queuedAgentRequest: null, queuedMessage: null, queuedMessageCourseId: null });
});

test("queue keeps the first pending request instead of overwriting it", () => {
  const state = useStore.getState();
  assert.equal(state.enqueueAgentRequest(first), "enqueued");
  assert.equal(state.enqueueAgentRequest({ ...first, requestId: "request-2", text: "生成教案" }), "conflict");
  assert.equal(useStore.getState().queuedAgentRequest?.requestId, "request-1");
});

test("consume is idempotent and only removes the matching request", () => {
  useStore.getState().enqueueAgentRequest(first);
  assert.equal(useStore.getState().consumeAgentRequest("other"), null);
  assert.equal(useStore.getState().queuedAgentRequest?.requestId, "request-1");

  assert.equal(useStore.getState().consumeAgentRequest("request-1")?.text, "生成报告");
  assert.equal(useStore.getState().consumeAgentRequest("request-1"), null);
  assert.equal(useStore.getState().queuedAgentRequest, null);
});

test("explicit clear can guard against clearing a newer request", () => {
  useStore.getState().enqueueAgentRequest(first);
  useStore.getState().clearQueuedAgentRequest("other");
  assert.equal(useStore.getState().queuedAgentRequest?.requestId, "request-1");
  useStore.getState().clearQueuedAgentRequest("request-1");
  assert.equal(useStore.getState().queuedAgentRequest, null);
});


test("ordinary queued message can only be consumed once", () => {
  useStore.getState().setQueuedMessage("规划课程知识库");

  assert.equal(
    useStore.getState().consumeQueuedMessage("规划课程知识库"),
    "规划课程知识库",
  );
  assert.equal(
    useStore.getState().consumeQueuedMessage("规划课程知识库"),
    null,
  );
  assert.equal(useStore.getState().queuedMessage, null);
});


test("course queued message waits for its target course workspace", () => {
  useStore.getState().enqueueCourseMessage("course-b", "规划课程知识库");

  assert.equal(
    useStore.getState().consumeQueuedMessage("规划课程知识库", "course-a"),
    null,
  );
  assert.equal(useStore.getState().queuedMessage, "规划课程知识库");
  assert.equal(
    useStore.getState().consumeQueuedMessage("规划课程知识库", "course-b"),
    "规划课程知识库",
  );
  assert.equal(useStore.getState().queuedMessage, null);
});
