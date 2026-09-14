import { expect, test } from './fixtures/teacherApp';

test('mind map starts with a balanced overview and preserves hidden nodes in export', async ({ teacherPage: page }) => {
  const root = { id: 'root', title: '主题', children: [
    { id: 'layout', title: '布局', children: [{ id: 'detail', title: '连续存储细节' }] },
    { id: 'address', title: '寻址' }, { id: 'capacity', title: '容量' }, { id: 'access', title: '随机访问' },
    { id: 'move', title: '移动代价' }, { id: 'resize', title: '动态扩容' }, { id: 'bounds', title: '边界检查' },
    { id: 'conditions', title: '前提' },
  ] };
  const materials = ['map-one', 'map-two'].map(material_id => ({ material_id, material_type: 'graph',
    course_id: 'course-physics', owner_user_id: 'teacher-a', visibility: 'private', version: 1,
    title: material_id, content: { root } }));
  await page.route('**/src/**', route => route.continue());
  await page.route('**/api/courses/course-physics/materials**', route => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({ json: materials.find(m => path.endsWith('/' + m.material_id)) || materials });
  });
  await page.goto('/#resources?course_id=course-physics&material_type=graph&material_id=map-one');
  await expect(page.locator('.balanced-mind-map__diagram')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.balanced-mind-map__side--left > .balanced-mind-map__branch')).toHaveCount(4);
  await expect(page.locator('.balanced-mind-map__side--right > .balanced-mind-map__branch')).toHaveCount(4);
  await expect(page.getByText('8 个主分支 · 10 个节点', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '展开布局', exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('寻址', { exact: true })).toBeVisible();
  await expect(page.getByText('前提', { exact: true })).toBeVisible();
  await expect(page.getByText('连续存储细节', { exact: true })).toHaveCount(0);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出导图', exact: true }).click();
  const stream = await (await download).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString()).root).toEqual(root);
  await page.getByRole('button', { name: '展开布局', exact: true }).click();
  await expect(page.getByText('连续存储细节', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '概览', exact: true }).click();
  await expect(page.getByText('连续存储细节', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '展开全部', exact: true }).click();
  await expect(page.getByText('连续存储细节', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '缩小', exact: true }).click();
  await page.getByRole('button', { name: '复位', exact: true }).click();
  await expect(page.getByText('连续存储细节', { exact: true })).toHaveCount(0);
  await expect(page.locator('.balanced-mind-map__zoom-controls')).toContainText('100%');
  await page.getByRole('button', { name: '展开布局', exact: true }).click();
  await page.evaluate(() => { location.hash = '#resources?course_id=course-physics&material_type=graph&material_id=map-two'; });
  await expect(page.getByRole('heading', { name: 'map-two', exact: true })).toBeVisible();
  await expect(page.getByText('连续存储细节', { exact: true })).toHaveCount(0);
});

for (const [kind, label] of [['lesson_plan', '教案'], ['blog', '博客'], ['quiz', '习题'], ['flashcard', '闪卡'], ['graph', '思维导图'], ['game', '互动游戏'], ['classroom', 'AI 课堂']]) {
  test(`${label} uses the appropriate interaction and submission progress`, async ({ teacherPage: page }) => {
    await page.route('**/src/**', route => route.continue());
    await page.route('**/api/personal-knowledge/documents**', route => route.fulfill({ json: [] }));
    const requests: any[] = [];
    const direct = ['quiz', 'flashcard', 'graph', 'game'].includes(kind);
    const outline = `# 数组：${label}大纲\n\n## 1. 内存布局\n\n### 1.1 连续存储\n\n## 2. 地址计算\n\n## 3. 练习检查`;
    const taskId = `private-job-${kind}`;
    await page.route('**/api/chat/v2/stream', route => {
      requests.push(route.request().postDataJSON());
      const first = !direct && requests.length === 1;
      const payload = { message: { role: 'assistant', content: first ? outline : `正在生成${label}，完成后会在这里显示。` },
        conversation: { conversation_id: `resource-${kind}` }, action: { name: `generate.${kind}` }, artifacts: [], sources: [],
        workflow: { type: kind, status: first ? 'awaiting_confirm' : 'running', stage: first ? 'outline' : 'generating' },
        ...(!first ? { task_id: taskId } : {}), trace: { path: 'deepseek-harness' } };
      const events = first ? [
        { type: 'tool_call', payload: { tool: 'draft_resource_outline', call_id: 'outline-call', args: { resource_type: kind } } },
        { type: 'delta', payload: { content: '模型另写的大纲' } },
      ] : [{ type: 'task_submitted', payload: { task_id: taskId, workflow_type: kind } },
           { type: 'delta', payload: { content: `submitted ${taskId}` } }];
      return route.fulfill({ contentType: 'text/event-stream', body: [...events, { type: 'result', payload }, { type: 'done', payload: {} }].map(e => `data: ${JSON.stringify(e)}\n\n`).join('') });
    });
    await page.goto('/#ai?course_id=course-physics');
    const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
    await input.fill(`生成数组${label}`); await input.press('Enter');
    if (!direct) {
      await expect(page.getByRole('heading', { name: '1. 内存布局', exact: true })).toBeVisible();
      await expect(page.getByText('模型另写的大纲')).toHaveCount(0);
      await input.fill('Go ahead'); await input.press('Enter');
    }
    await expect(page.getByText(`正在生成${label}，完成后会在这里显示。`, { exact: true })).toBeVisible();
    await expect(page.getByText(`submitted ${taskId}`)).toHaveCount(0);
    if (direct) {
      expect(requests).toHaveLength(1);
      await expect(page.getByRole('heading', { name: '1. 内存布局', exact: true })).toHaveCount(0);
    } else {
      expect(requests[1].conversation_id).toBe(`resource-${kind}`);
      await expect(page.getByRole('heading', { name: '1. 内存布局', exact: true })).toBeVisible();
    }
  });
}

test('switching resource links in the same course opens the requested result', async ({ teacherPage: page }) => {
  const common = { course_id: 'course-physics', owner_user_id: 'teacher-a', visibility: 'private', version: 1 };
  const materials = [
    { ...common, material_type: 'lesson_plan', material_id: 'lesson-one', title: '教案验收', content: '# 教案内容\n\n地址计算的课堂活动。' },
    { ...common, material_type: 'flashcard', material_id: 'cards-two', title: '闪卡验收', content: { cards: [{ front: '随机访问复杂度？', back: 'O(1)' }] } },
  ];
  await page.route('**/src/**', route => route.continue());
  await page.route('**/api/courses/course-physics/materials**', route => {
    const path = new URL(route.request().url()).pathname;
    const material = materials.find(item => path.endsWith(`/${item.material_type}/${item.material_id}`));
    return route.fulfill({ json: material || materials });
  });
  await page.goto('/#resources?course_id=course-physics&material_type=lesson_plan&material_id=lesson-one');
  await expect(page.getByRole('heading', { name: '教案内容', exact: true })).toBeVisible();
  await page.evaluate(() => { window.location.hash = '#resources?course_id=course-physics&material_type=flashcard&material_id=cards-two'; });
  const card = page.locator('.resource-flashcard-grid button');
  await expect(card).toContainText('随机访问复杂度？');
  await card.click();
  await expect(card).toContainText('O(1)');
  await expect(page.getByRole('heading', { name: '教案内容', exact: true })).toHaveCount(0);
});


test('native quiz export matches preview and fresh flashcards start on the front', async ({ teacherPage: page }) => {
  const questions = [{ id: 'q1', type: 'single_choice', stem: '2+3=?', options: ['5', '6'], answer: 'A', explanation: '二加三为五' }];
  const materials = [
    { material_id: 'quiz-native', material_type: 'quiz', title: '原生习题', content: { title: '原生习题', questions } },
    { material_id: 'cards-first', material_type: 'flashcard', title: '第一份', content: { cards: [{ front: '第一份正面', back: '第一份背面' }] } },
    { material_id: 'cards-second', material_type: 'flashcard', title: '第二份', content: { cards: [{ front: '第二份正面', back: '第二份背面' }] } },
  ];
  await page.route('**/src/**', route => route.continue());
  await page.route('**/api/courses/course-physics/materials**', route => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({ json: materials.map(m => ({ ...m, course_id: 'course-physics', owner_user_id: 'teacher-a', visibility: 'private', version: 1 })).find(m => path.endsWith('/' + m.material_id)) || materials.map(m => ({ ...m, course_id: 'course-physics', owner_user_id: 'teacher-a', visibility: 'private', version: 1 })) });
  });
  await page.goto('/#resources?course_id=course-physics&material_type=quiz&material_id=quiz-native');
  await expect(page.locator('.resource-quiz-preview')).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.resource-quiz-preview ol')).toHaveCSS('list-style-type', 'upper-alpha');
  await expect(page.locator('.resource-quiz-preview details')).not.toHaveAttribute('open');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出', exact: true }).click();
  const stream = await (await download).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString()).questions).toEqual(questions);
  await page.evaluate(() => { location.hash = '#resources?course_id=course-physics&material_type=flashcard&material_id=cards-first'; });
  const card = page.locator('.resource-flashcard-grid button');
  await expect(card).toContainText('第一份正面');
  await card.click();
  await expect(card).toContainText('第一份背面');
  await page.evaluate(() => { location.hash = '#resources?course_id=course-physics&material_type=flashcard&material_id=cards-second'; });
  await expect(card).toContainText('第二份正面');
  await expect(card).toHaveAttribute('aria-pressed', 'false');
});

for (const ending of ['late-result', 'disconnect']) {
  test(`lesson task releases input before stream ends and survives ${ending}`, async ({ teacherPage: page }) => {
    await page.route('**/src/**', route => route.continue());
    const now = new Date().toISOString();
    let finished = false;
    const job = { schema_version: 1, version: 1, edu_job_id: 'fast-lesson', kind: 'generate_lesson_plan',
      status: 'running', step: 'reviewing', progress: 25, message: '正在核对内容与教学要求',
      owner_user_id: 'teacher-a', course_id: 'course-physics', scope_type: 'course', scope_id: null,
      input_summary: { title: '数组教案' }, retryable: false, cancelable: true, created_at: now, updated_at: now };
    await page.route('**/api/jobs**', route => {
      const value = finished ? { ...job, version: 2, status: 'succeeded', progress: 100, finished_at: new Date().toISOString() } : job;
      return route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/fast-lesson') ? value : { items: [value], next_cursor: null, server_time: now } });
    });
    await page.route('**/api/chat/tasks/fast-lesson', route => route.fulfill({ json: { status: 'completed', result: {
      conversation: { conversation_id: 'fast-conversation' }, message: { role: 'assistant', content: '数组教案已生成完成。' },
      artifacts: [], sources: [], workflow: { type: 'lesson_plan', status: 'completed' },
    } } }));
    await page.addInitScript(({ ending }) => {
      const original = window.fetch.bind(window);
      let calls = 0;
      window.fetch = async (input, init) => {
        if (!String(input).includes('/api/chat/v2/stream')) return original(input, init);
        calls += 1;
        const encode = (type: string, payload: any) => new TextEncoder().encode(`data: ${JSON.stringify({ type, payload })}\n\n`);
        const result = (content: string) => ({ message: { role: 'assistant', content },
          conversation: { conversation_id: 'fast-conversation' }, artifacts: [], sources: [], action: { name: 'chat.reply' } });
        if (calls > 1) return new Response(new ReadableStream({ start(controller) {
          controller.enqueue(encode('result', result('数组元素按索引访问。'))); controller.close();
        } }), { headers: { 'Content-Type': 'text/event-stream' } });
        return new Response(new ReadableStream({ start(controller) {
          controller.enqueue(encode('metadata', { conversation_id: 'fast-conversation' }));
          controller.enqueue(encode('task_submitted', { task_id: 'fast-lesson', workflow_type: 'lesson_plan', conversation_id: 'fast-conversation' }));
          (window as any).finishLessonReply = () => {
            if (ending === 'disconnect') { controller.error(new Error('simulated disconnected stream')); return; }
            controller.enqueue(encode('status', { label: '迟到的状态' }));
            controller.enqueue(encode('delta', { content: '迟到的回复' }));
            controller.enqueue(encode('result', { ...result('迟到的回复'), task_id: 'fast-lesson', workflow: { type: 'lesson_plan', status: 'running' } }));
            controller.close();
          };
        } }), { headers: { 'Content-Type': 'text/event-stream' } });
      };
    }, { ending });
    await page.goto('/#ai?course_id=course-physics');
    const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
    await input.fill('按已确认的方案生成教案'); await input.press('Enter');
    await expect(page.getByText('正在生成教案，完成后会在这里显示。', { exact: true })).toBeVisible();
    await expect(input).toBeEnabled();
    await expect(page.getByText(/正在核对内容与教学要求 · 可以继续交流/)).toBeVisible();
    await input.fill('解释一下数组访问'); await input.press('Enter');
    await expect(page.getByText('数组元素按索引访问。', { exact: true })).toBeVisible();
    await page.evaluate(() => (window as any).finishLessonReply());
    await expect(page.getByText('迟到的回复', { exact: true })).toHaveCount(0);
    await expect(page.getByText('数组元素按索引访问。', { exact: true })).toBeVisible();
    finished = true;
    await expect(page.getByText('数组教案已生成完成。', { exact: true })).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('数组元素按索引访问。', { exact: true })).toBeVisible();
  });
}
