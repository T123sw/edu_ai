import { spawn, type ChildProcess } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

import {
  expect,
  chromium,
  test as base,
  type APIRequestContext,
  type APIResponse,
  type Page,
  type TestInfo,
} from "playwright/test";

export const learningApiPort = process.env.LEARNING_E2E_API_PORT || "18001";
export const learningApiBaseUrl = `http://127.0.0.1:${learningApiPort}`;
export const learningFrontendPort = process.env.LEARNING_E2E_FRONTEND_PORT || "15173";
export const learningFrontendBaseUrl = `http://127.0.0.1:${learningFrontendPort}`;
export const learningCourseId = "computational-thinking";
export const learningE2eTitle = `E2E-LOOP2-${Date.now()}`;

export type ApiEvidence = {
  label: string;
  method: string;
  url: string;
  status: number;
  body: unknown;
};

export type AgentEvidence = {
  actor: "teacher" | "student";
  answer: string;
  trace: Record<string, unknown>;
  structuredFacts: Record<string, unknown>;
};

type LearningBackend = {
  artifactDir: string;
  dbPath: string;
  frontendBaseUrl: string;
  restart(): Promise<void>;
};

type LearningFixtures = Record<string, never>;

type LearningWorkerFixtures = {
  learningBackend: LearningBackend;
};

function safeBody(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text.slice(0, 2_000);
  }
}

export async function captureApiEvidence(
  evidence: ApiEvidence[],
  label: string,
  response: APIResponse,
): Promise<unknown> {
  const text = await response.text();
  const body = safeBody(text);
  evidence.push({
    label,
    method: "APIRequestContext",
    url: response.url().replace(/Bearer\s+\S+/gi, "Bearer [redacted]"),
    status: response.status(),
    body,
  });
  return body;
}

export async function attachJsonEvidence(
  testInfo: TestInfo,
  name: string,
  value: unknown,
): Promise<void> {
  await testInfo.attach(name, {
    body: Buffer.from(JSON.stringify(value, null, 2), "utf8"),
    contentType: "application/json",
  });
}

export async function loginToken(
  request: APIRequestContext,
  username: string,
  password: string,
): Promise<string> {
  const response = await request.post(`${learningApiBaseUrl}/api/auth/login`, {
    data: { username, password },
  });
  expect(response.ok(), `login failed for ${username}: ${response.status()}`).toBeTruthy();
  return ((await response.json()) as { token: string }).token;
}

export async function loginAs(
  page: Page,
  username: string,
  password: string,
): Promise<void> {
  await page.goto("/#login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("账号", { exact: true }).fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText("登录 Edu AI")).toHaveCount(0);
}

export async function installDeterministicLearningAgent(
  page: Page,
  evidence: AgentEvidence[],
  options: {
    actor: "teacher" | "student";
    answer: string;
    structuredFacts: Record<string, unknown>;
    toolName: "get_course_learning_progress" | "get_my_learning_progress";
    failHistoricalConversation?: boolean;
  },
): Promise<void> {
  const staleConversationId = `conversation-stale-${options.actor}`;

  if (options.failHistoricalConversation) {
    await page.route(/\/api\/chat\/conversations(?:\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          conversations: [{
            conversation_id: staleConversationId,
            title: "旧生成任务 job_stale_should_not_leak",
            course_id: learningCourseId,
            scope_type: "course",
            scope_id: null,
            updated_at: "2026-08-10T00:00:00Z",
          }],
          total: 1,
        }),
      });
    });
    await page.route(`**/api/chat/conversations/${staleConversationId}`, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({ detail: "deterministic history recovery failure" }),
      }),
    );
  }

  await page.route("**/api/chat/v2/stream", async (route) => {
    const requestBody = route.request().postDataJSON() as { question?: string };
    const trace = {
      path: "agent",
      task_domain: "course_learning",
      agent_steps: [{ tool: options.toolName, ok: true }],
      model_gateway: "deterministic-learning-e2e",
      question: requestBody.question ?? "",
    };
    evidence.push({
      actor: options.actor,
      answer: options.answer,
      trace,
      structuredFacts: options.structuredFacts,
    });
    const conversationId = `conversation-learning-${options.actor}`;
    const result = {
      message: { role: "assistant", content: options.answer },
      conversation: { conversation_id: conversationId },
      action: { name: "chat.reply" },
      workflow: null,
      artifacts: [],
      sources: [],
      trace,
    };
    const frames = [
      // Keep the initial send bound to the current (new) conversation until the
      // final response adopts its persisted id. Sending a new id in this first
      // frame races React's store update and correctly causes the history guard
      // to discard the remaining frames as stale.
      { type: "metadata", payload: { sources: [] } },
      { type: "status", payload: { stage: "learning_status", label: "读取学习记录" } },
      { type: "tool_call", payload: { tool: options.toolName, args: {} } },
      { type: "tool_result", payload: { tool: options.toolName, ok: true, result: options.structuredFacts } },
      { type: "delta", payload: { content: options.answer } },
      { type: "result", payload: result },
      { type: "done", payload: { conversation_id: conversationId } },
    ];
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream; charset=utf-8",
      headers: { "Cache-Control": "no-cache" },
      body: `${frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join("")}`,
    });
  });
}

async function waitForUrl(url: string, label: string, timeoutMs = 45_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError = `${label} did not answer`;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = `${label} returned ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 250));
  }
  throw new Error(`isolated ${label} did not become ready: ${lastError}`);
}

async function waitForExit(child: ChildProcess, timeoutMs: number): Promise<boolean> {
  if (child.exitCode !== null) return true;
  return await new Promise<boolean>((resolvePromise) => {
    const timer = setTimeout(() => resolvePromise(false), timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolvePromise(true);
    });
  });
}

export const test = base.extend<LearningFixtures, LearningWorkerFixtures>({
  browser: [async ({}, use) => {
    const explicitExecutable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
    const systemCandidates = process.platform === "win32"
      ? [
          "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
          "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
          "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
          "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        ]
      : [];
    const executablePath = explicitExecutable
      || systemCandidates.find((candidate) => existsSync(candidate));
    const browser = await chromium.launch(executablePath ? { executablePath } : {});
    try {
      await use(browser);
    } finally {
      await browser.close();
    }
  }, { scope: "worker" }],
  learningBackend: [async ({}, use, workerInfo) => {
    const eduRoot = resolve(__dirname, "..", "..", "..");
    const apiSrc = resolve(eduRoot, "api", "src");
    const artifactDir = resolve(
      eduRoot,
      "test-results",
      "learning-loop",
      `worker-${workerInfo.parallelIndex}-${Date.now()}`,
    );
    mkdirSync(artifactDir, { recursive: true });
    const dbPath = resolve(artifactDir, "learning.db");
    const logPath = resolve(artifactDir, "backend.log");
    const frontendLogPath = resolve(artifactDir, "frontend.log");
    let backendChild: ChildProcess | null = null;
    let frontendChild: ChildProcess | null = null;

    const stopProcess = async (running: ChildProcess | null) => {
      if (!running || running.exitCode !== null) return;
      running.kill("SIGTERM");
      if (!(await waitForExit(running, 8_000))) {
        running.kill("SIGKILL");
        await waitForExit(running, 3_000);
      }
    };

    const stopBackend = async () => {
      await stopProcess(backendChild);
      backendChild = null;
    };

    const stop = async () => {
      await stopProcess(frontendChild);
      await stopBackend();
      frontendChild = null;
    };

    const startBackend = async () => {
      const python = process.env.PYTHON || process.env.PYTHON_BIN || "python";
      backendChild = spawn(
        python,
        ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", learningApiPort],
        {
          cwd: artifactDir,
          env: {
            ...process.env,
            PYTHONPATH: apiSrc,
            STORAGE_ROOT: resolve(artifactDir, "storage"),
            LEARNING_DB_PATH: dbPath,
            COURSE_MEMBERSHIPS_FILE: resolve(artifactDir, "course-memberships.json"),
            COURSE_STORAGE_ROOT: resolve(eduRoot, "api", "course_data"),
            DEV_AUTO_ENROLL_ALL_COURSES: "1",
            USER_PERSISTENCE_MODE: "json",
            COURSE_PERSISTENCE_MODE: "json",
            COURSE_MEMBERSHIP_PERSISTENCE_MODE: "json",
            USE_REACT_AGENT: process.env.LEARNING_E2E_REAL_MODEL === "1" ? "true" : "false",
          },
          stdio: ["ignore", "pipe", "pipe"],
          windowsHide: true,
        },
      );
      backendChild.stdout?.on("data", (chunk) => appendFileSync(logPath, chunk));
      backendChild.stderr?.on("data", (chunk) => appendFileSync(logPath, chunk));
      await waitForUrl(`${learningApiBaseUrl}/health`, "learning backend");
    };

    const startFrontend = async () => {
      frontendChild = spawn(
        process.execPath,
        [resolve(eduRoot, "node_modules", "vite", "bin", "vite.js"), "--host", "127.0.0.1", "--port", learningFrontendPort],
        {
          cwd: eduRoot,
          env: {
            ...process.env,
            VITE_API_BASE_URL: learningApiBaseUrl,
          },
          stdio: ["ignore", "pipe", "pipe"],
          windowsHide: true,
        },
      );
      frontendChild.stdout?.on("data", (chunk) => appendFileSync(frontendLogPath, chunk));
      frontendChild.stderr?.on("data", (chunk) => appendFileSync(frontendLogPath, chunk));
      await waitForUrl(learningFrontendBaseUrl, "learning frontend");
    };

    const start = async () => {
      await startBackend();
      await startFrontend();
    };

    try {
      try {
        const occupied = await fetch(`${learningApiBaseUrl}/health`);
        if (occupied.ok) {
          throw new Error(
            `port ${learningApiPort} is already serving a backend; stop it so E2E cannot accidentally use a non-isolated database`,
          );
        }
      } catch (error) {
        if (error instanceof Error && error.message.includes("already serving")) throw error;
      }
      try {
        const occupied = await fetch(learningFrontendBaseUrl);
        if (occupied.ok) {
          throw new Error(
            `port ${learningFrontendPort} is already serving a frontend; stop it so E2E cannot reuse stale code`,
          );
        }
      } catch (error) {
        if (error instanceof Error && error.message.includes("already serving")) throw error;
      }
      await start();
      await use({
        artifactDir,
        dbPath,
        frontendBaseUrl: learningFrontendBaseUrl,
        restart: async () => {
          await stopBackend();
          await startBackend();
        },
      });
    } finally {
      await stop();
    }
  }, { scope: "worker" }],
});

export { expect };
