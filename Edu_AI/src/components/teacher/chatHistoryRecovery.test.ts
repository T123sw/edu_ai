import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  ConversationLoadError,
  getChatConversationDetail,
  resolveConversationLoadError,
} from "../../services/teacher/api.ts";
import { recoverConversationFailure } from "./chatHistoryRecovery.ts";

test("failed active history is detached before a new agent turn", () => {
  assert.deepEqual(recoverConversationFailure("conv-bad", "conv-bad"), {
    nextConversationId: null,
    clearMessages: true,
    clearPendingTasks: true,
    retryable: true,
  });
});

test("failure for a non-active history does not clear current chat", () => {
  assert.equal(
    recoverConversationFailure("conv-good", "conv-bad").clearMessages,
    false,
  );
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

test("ChatPanel clears every active recovery reference but not global chat controls", () => {
  const panel = readFileSync(
    fileURLToPath(new URL("./ChatPanel.tsx", import.meta.url)),
    "utf8",
  );
  const activeCleanup = panel.match(/if \(decision\.clearMessages\) \{([\s\S]*?)\n      \}/u)?.[1] || "";
  const pendingCleanup = panel.match(/if \(decision\.clearPendingTasks\) \{([\s\S]*?)\n      \}/u)?.[1] || "";

  assert.match(activeCleanup, /setMessages\(\[\]\)/u);
  assert.match(activeCleanup, /setStatusCard\(null\)/u);
  assert.match(activeCleanup, /setWorkflowType\(null\)/u);
  assert.match(activeCleanup, /setWorkflowStatus\(null\)/u);
  assert.match(activeCleanup, /clearArtifactReference\(\)/u);
  assert.match(activeCleanup, /clearConversationReference\(\)/u);
  assert.match(activeCleanup, /clearConversationGeneratedFiles\(\)/u);
  assert.match(pendingCleanup, /setBackgroundTaskId\(null\)/u);
  assert.match(panel, /新建对话/u);
  assert.match(panel, /onClick=\{\(\) => void handleSendMessage\(\)\}/u);
});
