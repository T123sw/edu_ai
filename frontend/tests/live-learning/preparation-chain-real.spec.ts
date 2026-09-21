import { test, expect } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

// Configuration is read inside the test: discovery does not require secrets.
// A missing service/config is a test failure, never a switch to routed mock data.
test('fresh upload through workers to exact versions and real playback', async ({ page }, info) => {
  const credentialsFile = process.env.PREPARATION_TEST_CREDENTIALS_FILE;
  const uploadFile = process.env.PREPARATION_TEST_UPLOAD;
  expect(credentialsFile, 'private synthetic credentials required').toBeTruthy();
  expect(uploadFile, 'real DOCX fixture required').toBeTruthy();
  const credentials = JSON.parse(readFileSync(credentialsFile!, 'utf8'));
  expect(credentials.username).toMatch(/^prep-test-/);
  const sha = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  expect(execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim(), 'committed final build required').toBe('');
  const errors: string[] = [];
  const network: { method: string; path: string; status: number }[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('response', r => {
    if (r.status() >= 400) network.push({ method: r.request().method(), path: new URL(r.url()).pathname, status: r.status() });
  });
  await page.addInitScript(() => {
    const evidence = { decoded: 0, progressed: 0 };
    (window as any).__preparationAudio = evidence;
    document.addEventListener('loadeddata', e => { if (e.target instanceof HTMLMediaElement) evidence.decoded++; }, true);
    document.addEventListener('timeupdate', e => {
      if (e.target instanceof HTMLMediaElement && e.target.currentTime > 0.1) evidence.progressed++;
    }, true);
  });
  try {
    const buildResponse = await page.request.get('/preparation-build.json');
    expect(buildResponse.ok(), 'final build provenance required').toBeTruthy();
    expect(await buildResponse.json()).toMatchObject({ code_sha: sha });
    await page.goto('/');
    await page.getByLabel('账号', { exact: true }).fill(credentials.username);
    await page.getByLabel('密码', { exact: true }).fill(credentials.password);
    await page.getByRole('button', { name: /^登\s*录$/ }).click();
    await expect(page.getByRole('heading', { name: '最近学习' })).toBeVisible();
    const token = await page.evaluate(() => JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').token);
    expect(token).toBeTruthy();
    const headers = { Authorization: `Bearer ${token}` };
    const identityResponse = await page.request.get('/api/preparation-validation/identity', { headers });
    expect(identityResponse.ok(), 'test backend attestation unavailable').toBeTruthy();
    const identity = await identityResponse.json();
    expect(identity).toMatchObject({ code_sha: sha, dirty: false, worker_started: true, test_identity: credentials.username });
    expect(identity.database).toMatch(/^edu_ai_preparation_test_/);
    await info.attach('identity', { body: JSON.stringify(identity, null, 2), contentType: 'application/json' });

    const goal = process.env.PREPARATION_TEST_GOAL || '我会Python但没学过Agent。只根据附件做两个节点、共20分钟的中文入门课，每节点需要报告、习题和AI课堂。先用12加30举例，再解释工具调用原理。只手工追踪伪代码，不学真实API、SDK、面试或部署。';
    await page.getByLabel('学习知识点与目标').fill(goal);
    const uploaded = page.waitForResponse(r => r.url().endsWith('/api/course-preparations/uploads') && r.request().method() === 'POST');
    await page.getByLabel('添加资料').setInputFiles(uploadFile!);
    expect((await uploaded).status()).toBe(201);
    const submitted = page.waitForResponse(r => new URL(r.url()).pathname.replace(/^\/backend(?=\/)/, '') === '/api/course-preparations' && r.request().method() === 'POST');
    await page.getByRole('button', { name: '开始学习' }).click();
    const response = await submitted;
    expect(response.status()).toBe(202);
    const accepted = await response.json();
    expect(accepted.preparation_id).toBeTruthy();
    await info.attach('fresh-request', { body: JSON.stringify({ request: response.request().postDataJSON(), accepted }), contentType: 'application/json' });
    await page.reload();
    let final: any;
    await expect.poll(async () => {
      const r = await page.request.get(`/api/course-preparations/${accepted.preparation_id}`, { headers });
      expect(r.ok()).toBeTruthy(); final = await r.json();
      return ['succeeded', 'failed', 'canceled'].includes(final.status);
    }, { timeout: 1_800_000, intervals: [2000] }).toBe(true);
    await info.attach('public-state', { body: JSON.stringify(final), contentType: 'application/json' });
    expect(final.status).toBe('succeeded');
    expect(final.result_ref.course_ready).toBe(true);
    const courseId = final.result_ref.course_id;
    const currentEntry = page.locator(`a[href="#/classroom/${courseId}"]`);
    await expect(currentEntry).toBeVisible(); await currentEntry.click();
    const roomResponse = await page.request.get(`/api/self-learning/courses/${courseId}`, { headers });
    expect(roomResponse.ok()).toBeTruthy();
    const room = await roomResponse.json();
    await info.attach('fresh-room', { body: JSON.stringify(room, null, 2), contentType: 'application/json' });
    expect(room.chapters).toHaveLength(2);
    for (const chapter of room.chapters) {
      const required = chapter.resources.filter((r: any) => r.ready);
      expect(new Set(required.map((r: any) => r.remote.materialType))).toEqual(new Set(['report', 'quiz', 'classroom']));
      for (const resource of required) {
        const { materialType: kind, materialId: mid, version } = resource.remote;
        expect(version).toBeGreaterThan(0);
        const exact = await page.request.get(`/api/self-learning/courses/${courseId}/materials/${kind}/${mid}/versions/${version}`, { headers });
        expect(exact.ok()).toBeTruthy(); const material = await exact.json(); expect(material.version).toBe(version);
        await page.goto(`/#/classroom/${courseId}?resource=${resource.id}`);
        const frame = page.frameLocator('iframe.sl-live-material');
        if (kind === 'quiz') {
          const question = frame.getByRole('region', { name: '理解检查', exact: true }).first();
          await expect(question.locator('input, textarea').first()).toBeVisible({ timeout: 30_000 });
          const stem = await question.locator(':scope > p').first().innerText();
          const shortAnswer = await question.getByRole('textbox', { name: '检查答案' }).count() > 0;
          const answerText = '我的理解：模型选择工具，程序校验参数并执行；缺少参数时不执行。';
          if (shortAnswer) await question.getByRole('textbox', { name: '检查答案' }).fill(answerText);
          else await question.locator('input').first().check();
          await question.getByRole('button', { name: '提交检查答案' }).click();
          await expect(question.getByRole('status')).toContainText(/本题|答案已保存/, { timeout: 30_000 });
          const savedAnswer = question.getByRole('group', { name: '已保存的作答' });
          if (shortAnswer) await expect(savedAnswer).toContainText(answerText);
          else await expect(savedAnswer.locator('input').first()).toBeChecked();
          await page.reload();
          await expect(question.locator(':scope > p').first()).toHaveText(stem, { timeout: 30_000 });
          await expect(question.getByRole('status')).toContainText(/本题|答案已保存/, { timeout: 30_000 });
          if (shortAnswer) {
            await expect(savedAnswer).toContainText(answerText);
            await expect(question.getByRole('textbox', { name: '检查答案' })).toHaveCount(0);
          } else {
            await expect(savedAnswer.locator('input').first()).toBeChecked();
            await expect(savedAnswer.locator('input').first()).toBeDisabled();
          }
        } else if (kind === 'classroom') {
          expect(material.scenes.length).toBeGreaterThan(0);
          for (let index = 0; index < material.scenes.length; index++) {
            await expect(frame.locator('.classroom-page-count')).toHaveText(`${index + 1} / ${material.scenes.length}`);
            const scene = material.scenes[index];
            if (scene.type === 'quiz') {
              await expect(frame.getByText(/正确答案：/)).toHaveCount(0);
              await expect(frame.getByRole('radio').first()).toBeVisible();
              await frame.getByRole('radio').first().check();
              await frame.getByRole('button', { name: '提交并查看解析', exact: true }).click();
              await expect(frame.getByText(/正确答案：/).first()).toBeVisible();
              await expect(frame.getByText(/回答正确|回答有误/).first()).toBeVisible();
            }
            if (scene.actions?.some((a: any) => a.type === 'speech')) {
              await frame.getByRole('button', { name: /^(播放当前页|重新播放当前页|重播当前页)$/ }).click();
              await expect(frame.locator('.classroom-subtitle')).toBeVisible();
              const initial = await frame.locator('.classroom-subtitle').innerText();
              // The actual narration/page state must advance, clicking alone never passes.
              await expect.poll(async () => ({
                narration: await frame.locator('.classroom-subtitle').textContent().catch(() => null),
                page: await frame.locator('.classroom-page-count').innerText(),
              }), { timeout: 120_000 }).not.toEqual({ narration: initial, page: `${index + 1} / ${material.scenes.length}` });
            }
            const images = frame.locator('img');
            for (const img of await images.all()) await expect.poll(() => img.evaluate((e: HTMLImageElement) => e.complete && e.naturalWidth > 0)).toBe(true);
            expect(await frame.locator('body').evaluate(e => e.scrollWidth <= e.clientWidth + 2), 'horizontal overflow').toBe(true);
            await page.screenshot({ path: info.outputPath(`${chapter.id}-${kind}-${version}-page${index + 1}.png`) });
            if (index < material.scenes.length - 1) {
              const count = await frame.locator('.classroom-page-count').innerText();
              if (count.startsWith(`${index + 1} /`)) await frame.getByRole('button', { name: '下一页', exact: true }).click();
            }
          }
          if (process.env.PREPARATION_REQUIRE_AUDIO === '1') {
            const iframe = await page.locator('iframe.sl-live-material').elementHandle();
            const content = await iframe!.contentFrame();
            const audio = await content!.evaluate(() => (window as any).__preparationAudio);
            expect(audio.decoded, 'actual media decode required').toBeGreaterThan(0);
            expect(audio.progressed, 'actual media clock progress required').toBeGreaterThan(0);
          }
        } else await expect(frame.locator('[data-reading-end]')).toBeAttached();
        await page.screenshot({ path: info.outputPath(`${chapter.id}-${kind}-${version}.png`) });
      }
    }
    expect(errors).toEqual([]); expect(network).toEqual([]);
  } finally {
    await info.attach('console-errors', { body: JSON.stringify(errors), contentType: 'application/json' });
    await info.attach('network-errors', { body: JSON.stringify(network), contentType: 'application/json' });
  }
});
