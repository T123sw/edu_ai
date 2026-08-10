import { expect, test, type APIRequestContext, type Page } from 'playwright/test';

const enabled = process.env.REAL_QA_E2E === '1';
const apiBase = process.env.REAL_QA_API_BASE || 'http://127.0.0.1:18001';
const courseId = process.env.REAL_QA_COURSE_ID || 'computational-thinking';
const classroomId = process.env.REAL_QA_CLASSROOM_ID || 'IwhZs0-46W';

type AuthSession = {
  token: string;
  user: { username: string; role: 'student' };
};

async function login(
  request: APIRequestContext,
  username: string,
  password: string,
): Promise<AuthSession> {
  const response = await request.post(`${apiBase}/api/auth/login`, {
    data: { username, password },
  });
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  return {
    token: payload.access_token || payload.token,
    user: payload.user,
  };
}

async function installSession(
  page: Page,
  session: AuthSession,
  options: { reusableTurnId?: string; mockBrowserSpeech?: boolean } = {},
) {
  const reuseClientTurnId =
    options.reusableTurnId ?? process.env.REAL_QA_REUSE_CLIENT_TURN_ID ?? '';
  await page.addInitScript(({ auth, reusableTurnId, mockBrowserSpeech }) => {
    window.localStorage.setItem('edu-ai-auth', JSON.stringify(auth));
    window.localStorage.setItem('stitch-theme', 'ocean');
    if (reusableTurnId) {
      Object.defineProperty(window.crypto, 'randomUUID', {
        configurable: true,
        value: () => reusableTurnId,
      });
    }
    if (mockBrowserSpeech) {
      window.speechSynthesis.speak = (utterance) => {
        window.setTimeout(() => utterance.onend?.(new Event('end') as never), 20);
      };
    }

    const originalPlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function acceleratedPlay() {
      this.muted = true;
      this.playbackRate = 4;
      return originalPlay.call(this);
    };
  }, {
    auth: session,
    reusableTurnId: reuseClientTurnId,
    mockBrowserSpeech: Boolean(options.mockBrowserSpeech),
  });
}

test.describe('real classroom QA acceptance', () => {
  test.skip(!enabled, 'Set REAL_QA_E2E=1 to run against the real backend and Qwen TTS.');

  test('interrupts, speaks through protected audio, resumes, persists, and isolates', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    const studentA = await login(request, 'student', 'student123');
    await installSession(page, studentA);

    const question =
      process.env.REAL_QA_REUSE_QUESTION ||
      `为什么快速排序需要选基准值？验收标识 ${Date.now()}`;
    await page.goto(
      `/#classroom-player?course_id=${courseId}&classroom_id=${classroomId}`,
      { waitUntil: 'domcontentloaded' },
    );

    const playButton = page.getByRole('button', { name: '播放当前页' });
    await expect(playButton).toBeVisible({ timeout: 60_000 });
    await playButton.click();

    await expect(page.getByRole('complementary', { name: '课堂实时问答' })).toBeVisible();
    const questionBox = page.getByRole('textbox', { name: '课堂问题' });
    await questionBox.fill(question);

    const turnResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().includes(`/classrooms/${classroomId}/qa/turns`),
      { timeout: 180_000 },
    );
    const audioResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes('/qa/sessions/') &&
        response.url().includes('/audio/'),
      { timeout: 180_000 },
    );
    await page.getByRole('button', { name: '发送' }).click();
    await expect(page.getByText(question)).toBeVisible();
    await expect(questionBox).toBeDisabled();

    const turnResponse = await turnResponsePromise;
    expect(turnResponse.status()).toBe(200);
    const submittedRequest = turnResponse.request().postDataJSON();
    const submission = await turnResponse.json();
    expect(submission.turn.tts_status).toBe('ready');
    expect(submission.turn.audio_url).toMatch(/^\/api\//);
    expect(submission.turn.audio_url).not.toContain('localhost:3000');
    console.info(
      'REAL_QA_EVIDENCE',
      JSON.stringify({
        courseId,
        classroomId,
        sceneId: submittedRequest.checkpoint.scene_id,
        actionId: submittedRequest.checkpoint.action_id,
        checkpointPhase: submittedRequest.checkpoint.phase,
        turnId: submission.turn.turn_id,
        ttsStatus: submission.turn.tts_status,
      }),
    );

    const audioResponse = await audioResponsePromise;
    expect(audioResponse.status()).toBe(200);
    expect(audioResponse.headers()['content-type']).toMatch(/^audio\//);
    await expect(page.getByText(submission.turn.answer_text).last()).toBeVisible();
    await expect(page.getByText('可以输入问题，发送时会暂停课堂。')).toBeVisible({
      timeout: 90_000,
    });
    await expect(page.getByRole('button', { name: '暂停' })).toBeEnabled();

    const panel = page.locator('.classroom-qa-panel');
    const controls = page.getByTestId('classroom-core-controls');
    const widePanelBox = await panel.boundingBox();
    const wideControlsBox = await controls.boundingBox();
    expect(widePanelBox).not.toBeNull();
    expect(wideControlsBox).not.toBeNull();
    expect(widePanelBox!.y + widePanelBox!.height).toBeLessThanOrEqual(
      wideControlsBox!.y + 2,
    );

    await page.getByRole('button', { name: '进入演示' }).click();
    await expect(page.getByRole('button', { name: '退出演示' })).toBeVisible();
    await expect(panel).toBeVisible();
    await page.getByRole('button', { name: '退出演示' }).click();

    await page.setViewportSize({ width: 720, height: 900 });
    await expect(panel).toBeVisible();
    const narrowPanelBox = await panel.boundingBox();
    const narrowControlsBox = await controls.boundingBox();
    expect(narrowPanelBox).not.toBeNull();
    expect(narrowControlsBox).not.toBeNull();
    expect(narrowPanelBox!.y + narrowPanelBox!.height).toBeLessThanOrEqual(
      narrowControlsBox!.y + 2,
    );

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('button', { name: '播放当前页' })).toBeVisible({
      timeout: 60_000,
    });
    await page.getByRole('button', { name: '播放当前页' }).click();
    await expect(page.getByText(question)).toBeVisible();

    const studentBName = `qa-student-b-${Date.now()}`;
    const register = await request.post(`${apiBase}/api/auth/register`, {
      data: {
        username: studentBName,
        password: 'student12345',
        role: 'student',
      },
    });
    expect(register.ok()).toBeTruthy();
    const studentB = await login(request, studentBName, 'student12345');
    const headersB = { Authorization: `Bearer ${studentB.token}` };
    const sessionBResponse = await request.get(
      `${apiBase}/api/courses/${courseId}/classrooms/${classroomId}/qa/session`,
      { headers: headersB },
    );
    expect(sessionBResponse.status()).toBe(200);
    const sessionB = await sessionBResponse.json();
    expect(sessionB.turns).toHaveLength(0);

    const crossOwnerAudio = await request.get(
      `${apiBase}${submission.turn.audio_url}`,
      { headers: headersB },
    );
    expect(crossOwnerAudio.status()).toBe(404);

    const ownerAudio = await request.get(
      `${apiBase}${submission.turn.audio_url}`,
      { headers: { Authorization: `Bearer ${studentA.token}` } },
    );
    expect(ownerAudio.status()).toBe(200);
    expect((await ownerAudio.body()).byteLength).toBeGreaterThan(1_000);
  });

  test('degraded server TTS falls back to browser speech and resumes', async ({
    page,
    request,
  }) => {
    const degradedTurnId = process.env.REAL_QA_DEGRADED_CLIENT_TURN_ID;
    const degradedQuestion = process.env.REAL_QA_DEGRADED_QUESTION;
    test.skip(
      !degradedTurnId || !degradedQuestion,
      'Provide one persisted real TTS-failed turn to verify browser fallback.',
    );
    test.setTimeout(120_000);

    const student = await login(request, 'student', 'student123');
    await installSession(page, student, {
      reusableTurnId: degradedTurnId,
      mockBrowserSpeech: true,
    });
    await page.goto(
      `/#classroom-player?course_id=${courseId}&classroom_id=${classroomId}`,
      { waitUntil: 'domcontentloaded' },
    );
    await page.getByRole('button', { name: '播放当前页' }).click();
    await page.getByRole('textbox', { name: '课堂问题' }).fill(degradedQuestion);

    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().includes(`/classrooms/${classroomId}/qa/turns`),
    );
    await page.getByRole('button', { name: '发送' }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(200);
    const submission = await response.json();
    expect(submission.turn.tts_status).toBe('failed');
    expect(submission.turn.audio_url).toBeNull();
    await expect(page.getByText('可以输入问题，发送时会暂停课堂。')).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByRole('button', { name: '暂停' })).toBeEnabled();
  });
});
