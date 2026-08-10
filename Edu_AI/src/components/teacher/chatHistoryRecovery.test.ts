import assert from "node:assert/strict";
import test from "node:test";

import {
  ConversationLoadError,
  getChatConversationDetail,
  resolveConversationLoadError,
} from "../../services/teacher/api.ts";
import {
  applyConversationRecoveryFailure,
  createConversationAsyncGuard,
  recoverConversationFailure,
  resolveConversationRecoveryErrorAction,
  type ConversationAsyncGuard,
  type ConversationLoadToken,
  type ConversationSendToken,
} from "./chatHistoryRecovery.ts";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function consumeLoad<T>(
  guard: ConversationAsyncGuard,
  token: ConversationLoadToken,
  promise: Promise<T>,
  writes: string[],
  label: string,
) {
  try {
    await promise;
    guard.commitLoad(token, () => writes.push(`${label}:success`));
  } catch {
    guard.commitLoad(token, () => writes.push(`${label}:failure`));
  } finally {
    if (guard.isLatestLoad(token)) writes.push(`${label}:finally`);
  }
}

async function bindLatePendingTask(
  guard: ConversationAsyncGuard,
  sendToken: ConversationSendToken,
  pendingTask: Promise<string>,
  currentConversationId: () => string | null,
) {
  const taskId = await pendingTask;
  return guard.bindBackgroundTaskForSend(
    sendToken,
    taskId,
    currentConversationId(),
  );
}

test("failed active history is detached before a new agent turn", () => {
  assert.deepEqual(recoverConversationFailure("conv-bad", "conv-bad"), {
    nextConversationId: null,
    clearMessages: true,
    clearPendingTasks: true,
    retryable: true,
  });
});

test("failure for a non-active history does not clear current chat", () => {
  assert.deepEqual(recoverConversationFailure("conv-good", "conv-bad"), {
    nextConversationId: "conv-good",
    clearMessages: false,
    clearPendingTasks: false,
    retryable: true,
  });
});

test("active recovery failure clears injected store state and detaches the id", () => {
  const state = {
    conversationId: "conv-bad" as string | null,
    messages: ["stale"],
    workflow: "running" as string | null,
    pendingTask: "task-stale" as string | null,
    error: null as null | { conversationId: string },
  };
  applyConversationRecoveryFailure(
    state.conversationId,
    "conv-bad",
    { message: "无法加载这段历史对话，请重试", retryable: true },
    {
      clearRecoveredConversationState: () => {
        state.messages = [];
        state.workflow = null;
      },
      clearPendingTasks: () => { state.pendingTask = null; },
      setCurrentConversationId: (conversationId) => { state.conversationId = conversationId; },
      setError: (error) => { state.error = error; },
    },
  );

  assert.deepEqual(state, {
    conversationId: null,
    messages: [],
    workflow: null,
    pendingTask: null,
    error: {
      conversationId: "conv-bad",
      message: "无法加载这段历史对话，请重试",
      retryable: true,
    },
  });
});

test("non-active recovery failure leaves injected current chat state untouched", () => {
  const state = {
    conversationId: "conv-good" as string | null,
    clearCount: 0,
    pendingClearCount: 0,
  };
  applyConversationRecoveryFailure(
    state.conversationId,
    "conv-bad",
    { message: "这段历史对话已不存在", retryable: false },
    {
      clearRecoveredConversationState: () => { state.clearCount += 1; },
      clearPendingTasks: () => { state.pendingClearCount += 1; },
      setCurrentConversationId: (conversationId) => { state.conversationId = conversationId; },
      setError: () => undefined,
    },
  );

  assert.deepEqual(state, {
    conversationId: "conv-good",
    clearCount: 0,
    pendingClearCount: 0,
  });
});

test("dismiss clears the local error and retry targets its failed conversation", () => {
  const error = {
    conversationId: "conv-bad",
    message: "无法加载这段历史对话，请重试",
    retryable: true,
  };
  assert.deepEqual(resolveConversationRecoveryErrorAction(error, "dismiss"), {
    nextError: null,
    retryConversationId: null,
  });
  assert.deepEqual(resolveConversationRecoveryErrorAction(error, "retry"), {
    nextError: error,
    retryConversationId: "conv-bad",
  });
});

test("conversation detail errors expose stable user messages", () => {
  assert.deepEqual(resolveConversationLoadError(null), {
    message: "无法加载这段历史对话，请重试",
    retryable: true,
  });
  assert.deepEqual(resolveConversationLoadError(401), {
    message: "登录状态或权限已变化，请重新登录",
    retryable: false,
  });
  assert.deepEqual(resolveConversationLoadError(403), {
    message: "登录状态或权限已变化，请重新登录",
    retryable: false,
  });
  assert.deepEqual(resolveConversationLoadError(404), {
    message: "这段历史对话已不存在",
    retryable: false,
  });

  const error = new ConversationLoadError("稳定文案", true, 500);
  assert.equal(error.name, "ConversationLoadError");
  assert.equal(error.message, "稳定文案");
  assert.equal(error.retryable, true);
  assert.equal(error.status, 500);
});

test("conversation detail request hides network and HTTP diagnostics", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response("sensitive backend detail", { status: 403 });
    await assert.rejects(
      getChatConversationDetail("conv-forbidden"),
      (error: unknown) => error instanceof ConversationLoadError
        && error.message === "登录状态或权限已变化，请重新登录"
        && !error.message.includes("sensitive backend detail"),
    );

    globalThis.fetch = async () => {
      throw new TypeError("Failed to fetch");
    };
    await assert.rejects(
      getChatConversationDetail("conv-offline"),
      (error: unknown) => error instanceof ConversationLoadError
        && error.message === "无法加载这段历史对话，请重试"
        && !error.message.includes("Failed to fetch"),
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("slow A cannot overwrite fast B or clear B loading state", async () => {
  const guard = createConversationAsyncGuard("conv-origin");
  const writes: string[] = [];
  const slowA = deferred<string>();
  const fastB = deferred<string>();
  const tokenA = guard.startLoad("conv-a");
  const consumeA = consumeLoad(guard, tokenA, slowA.promise, writes, "a");
  const tokenB = guard.startLoad("conv-b");
  const consumeB = consumeLoad(guard, tokenB, fastB.promise, writes, "b");

  fastB.resolve("b");
  await consumeB;
  slowA.resolve("a");
  await consumeA;

  assert.deepEqual(writes, ["b:success", "b:finally"]);
});

test("A failure cannot replace B success with a stale local error", async () => {
  const guard = createConversationAsyncGuard("conv-origin");
  const writes: string[] = [];
  const slowA = deferred<string>();
  const fastB = deferred<string>();
  const consumeA = consumeLoad(guard, guard.startLoad("conv-a"), slowA.promise, writes, "a");
  const consumeB = consumeLoad(guard, guard.startLoad("conv-b"), fastB.promise, writes, "b");

  fastB.resolve("b");
  await consumeB;
  slowA.reject(new Error("a failed"));
  await consumeA;

  assert.deepEqual(writes, ["b:success", "b:finally"]);
});

test("newer same-conversation failure rejects an older success", async () => {
  const guard = createConversationAsyncGuard("conv-a");
  const writes: string[] = [];
  const oldSuccess = deferred<string>();
  const newFailure = deferred<string>();
  const consumeOld = consumeLoad(guard, guard.startLoad("conv-a"), oldSuccess.promise, writes, "old");
  const consumeNew = consumeLoad(guard, guard.startLoad("conv-a"), newFailure.promise, writes, "new");

  newFailure.reject(new Error("new failed"));
  await consumeNew;
  oldSuccess.resolve("old success");
  await consumeOld;

  assert.deepEqual(writes, ["new:failure", "new:finally"]);
});

test("new conversation invalidates an in-flight history response", async () => {
  const guard = createConversationAsyncGuard("conv-a");
  const writes: string[] = [];
  const oldLoad = deferred<string>();
  const consumeOld = consumeLoad(guard, guard.startLoad("conv-a"), oldLoad.promise, writes, "old");

  guard.invalidateConversation(null);
  oldLoad.resolve("old success");
  await consumeOld;

  assert.deepEqual(writes, []);
});

test("clearing active recovery prevents an already-started background poll write", async () => {
  const guard = createConversationAsyncGuard("conv-a");
  const writes: string[] = [];
  const poll = deferred<string>();
  const taskToken = guard.bindBackgroundTask("task-a", "conv-a");
  const consumePoll = (async () => {
    await poll.promise;
    guard.commitBackgroundTask(taskToken, "conv-a", () => writes.push("old-poll"));
  })();

  const loadToken = guard.startLoad("conv-a", { invalidateBackgroundTasks: false });
  const decision = recoverConversationFailure("conv-a", "conv-a");
  assert.equal(guard.commitLoad(loadToken, () => {
    guard.invalidateBackgroundTasks(decision.nextConversationId);
    guard.restoreConversation(decision.nextConversationId);
    writes.push("recovery");
  }), true);
  poll.resolve("done");
  await consumePoll;

  assert.deepEqual(writes, ["recovery"]);
});

test("new conversation and switch invalidate an in-flight background poll", async () => {
  for (const invalidate of [
    (guard: ConversationAsyncGuard) => guard.invalidateConversation(null),
    (guard: ConversationAsyncGuard) => guard.startLoad("conv-b"),
  ]) {
    const guard = createConversationAsyncGuard("conv-a");
    const writes: string[] = [];
    const poll = deferred<string>();
    const taskToken = guard.bindBackgroundTask("task-a", "conv-a");
    const consumePoll = (async () => {
      await poll.promise;
      guard.commitBackgroundTask(taskToken, "conv-a", () => writes.push("old-poll"));
    })();
    invalidate(guard);
    poll.resolve("done");
    await consumePoll;
    assert.deepEqual(writes, []);
  }
});

test("a newer task in the same conversation invalidates an older poll", async () => {
  const guard = createConversationAsyncGuard("conv-a");
  const writes: string[] = [];
  const poll = deferred<string>();
  const oldTaskToken = guard.bindBackgroundTask("task-old", "conv-a");
  const consumePoll = (async () => {
    await poll.promise;
    guard.commitBackgroundTask(oldTaskToken, "conv-a", () => writes.push("old-poll"));
  })();

  guard.bindBackgroundTask("task-new", "conv-a");
  poll.resolve("done");
  await consumePoll;

  assert.deepEqual(writes, []);
});

test("late pending task cannot bind after its send context is invalidated", async () => {
  for (const scenario of [
    {
      invalidate: (guard: ConversationAsyncGuard) => guard.invalidateConversation(null),
      nextConversationId: null,
    },
    {
      invalidate: (guard: ConversationAsyncGuard) => guard.startLoad("conv-b"),
      nextConversationId: "conv-b",
    },
  ]) {
    const guard = createConversationAsyncGuard("conv-a");
    const pendingTask = deferred<string>();
    const sendToken = guard.captureSend("conv-a");
    let currentConversationId: string | null = "conv-a";
    const binding = bindLatePendingTask(
      guard,
      sendToken,
      pendingTask.promise,
      () => currentConversationId,
    );

    scenario.invalidate(guard);
    currentConversationId = scenario.nextConversationId;
    pendingTask.resolve("task-late");

    let pollStarted = false;
    const writes: string[] = [];
    const taskToken = await binding;
    if (taskToken) {
      pollStarted = true;
      guard.commitBackgroundTask(taskToken, currentConversationId, () => writes.push("late-poll"));
    }
    assert.equal(taskToken, null);
    assert.equal(pollStarted, false);
    assert.deepEqual(writes, []);
  }
});

test("late pending task binds while its original send context is current", async () => {
  const guard = createConversationAsyncGuard("conv-a");
  const pendingTask = deferred<string>();
  const sendToken = guard.captureSend("conv-a");
  const binding = bindLatePendingTask(
    guard,
    sendToken,
    pendingTask.promise,
    () => "conv-a",
  );

  pendingTask.resolve("task-current");
  const taskToken = await binding;

  assert.equal(taskToken?.taskId, "task-current");
  assert.equal(
    taskToken
      ? guard.commitBackgroundTask(taskToken, "conv-a", () => undefined)
      : false,
    true,
  );
});
