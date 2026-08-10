import { expect, type Page } from 'playwright/test';
import { test } from './fixtures/teacherApp';

const courseId = 'course-physics';
const classroomId = 'classroom-persistent-qa';
const apiOrigin = 'http://localhost:8001';

function classroomMaterial() {
  return {
    material_id: classroomId,
    material_type: 'classroom',
    course_id: courseId,
    title: '连续授课与实时问答验收课堂',
    voice_status: 'ready',
    stage: { id: classroomId, name: '连续授课与实时问答验收课堂' },
    scenes_count: 3,
    scenes: [
      {
        id: 'scene-1',
        type: 'slide',
        title: '第一页：选择基准',
        order: 0,
        content: {
          type: 'slide',
          canvas: {
            id: 'canvas-1',
            elements: [{ id: 'title-1', type: 'text', text: '选择基准' }],
          },
        },
        actions: [{ id: 'speech-1', type: 'speech', text: '第一页慢速讲解' }],
      },
      {
        id: 'scene-2',
        type: 'slide',
        title: '第二页：完成分区',
        order: 1,
        content: {
          type: 'slide',
          canvas: {
            id: 'canvas-2',
            elements: [{ id: 'title-2', type: 'text', text: '完成分区' }],
          },
        },
        actions: [{ id: 'speech-2', type: 'speech', text: '第二页慢速讲解' }],
      },
      {
        id: 'scene-3',
        type: 'slide',
        title: '第三页：递归处理',
        order: 2,
        content: {
          type: 'slide',
          canvas: {
            id: 'canvas-3',
            elements: [{ id: 'title-3', type: 'text', text: '递归处理' }],
          },
        },
        actions: [{ id: 'speech-3', type: 'speech', text: '第三页慢速讲解' }],
      },
    ],
  };
}

async function installClassroomRoutes(page: Page, answerDelayMs = 700) {
  await page.route(`${apiOrigin}/api/courses/${courseId}/classrooms/${classroomId}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(classroomMaterial()) }),
  );
  await page.route(`${apiOrigin}/api/courses/${courseId}/classrooms/${classroomId}/qa/session`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'session-e2e',
        course_id: courseId,
        classroom_id: classroomId,
        owner_user_id: 'teacher-a',
        status: 'ready',
        turns: [],
      }),
    }),
  );
  await page.route(`${apiOrigin}/api/courses/${courseId}/classrooms/${classroomId}/qa/turns`, async (route) => {
    const request = route.request().postDataJSON() as { client_turn_id: string; question: string };
    await new Promise((resolve) => setTimeout(resolve, answerDelayMs));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: 'session-e2e',
        turn: {
          turn_id: 'turn-e2e',
          client_turn_id: request.client_turn_id,
          question: request.question,
          answer_text: '基准值把序列分成较小和较大的两部分。',
          transition_text: '理解基准后，我们继续刚才的分区过程。',
          tts_status: 'failed',
          audio_url: null,
          created_at: '2026-08-11T00:00:00+08:00',
        },
      }),
    });
  });
}

async function installSpeechMock(page: Page, durationFor: (text: string) => number) {
  await page.addInitScript((durations) => {
    window.speechSynthesis.cancel = () => undefined;
    window.speechSynthesis.getVoices = () => [];
    window.speechSynthesis.speak = (utterance) => {
      const text = utterance.text || '';
      const delay = text.includes('第一页')
        ? durations.first
        : text.includes('第二页')
          ? durations.second
          : text.includes('第三页')
            ? durations.third
            : durations.answer;
      window.setTimeout(() => utterance.onend?.(new Event('end') as never), delay);
    };
  }, {
    first: durationFor('第一页'),
    second: durationFor('第二页'),
    third: durationFor('第三页'),
    answer: durationFor('回答'),
  });
}

test.describe('persistent classroom QA', () => {
  test('shows the student turn immediately on the right and resumes after answering', async ({ teacherPage: page }) => {
    await installClassroomRoutes(page);
    await installSpeechMock(page, (text) => (text === '回答' ? 30 : 10_000));
    await page.goto(`/#classroom-player?course_id=${courseId}&classroom_id=${classroomId}`);

    const panel = page.getByRole('complementary', { name: '课堂实时问答' });
    await expect(panel).toBeVisible();
    await expect(page.getByRole('textbox', { name: '课堂问题' })).toBeEnabled();
    await page.getByRole('textbox', { name: '课堂问题' }).fill('播放前草稿不会打断课堂');
    await expect(page.getByRole('button', { name: '发送' })).toBeDisabled();
    await page.getByRole('button', { name: '播放当前页' }).click();

    const question = '快速排序为什么需要基准值？';
    const questionBox = page.getByRole('textbox', { name: '课堂问题' });
    await questionBox.fill(question);
    await page.getByRole('button', { name: '发送' }).click();

    const studentBubble = page.locator('.classroom-qa-turn__question');
    const aiBubble = page.locator('.classroom-qa-turn__answer');
    await expect(studentBubble.getByText(question)).toBeVisible({ timeout: 250 });
    await expect(aiBubble.getByText('正在结合当前讲解回答…')).toBeVisible();
    const studentBox = await studentBubble.locator('p').boundingBox();
    const aiBox = await aiBubble.locator('div').first().boundingBox();
    expect(studentBox).not.toBeNull();
    expect(aiBox).not.toBeNull();
    expect(studentBox!.x).toBeGreaterThan(aiBox!.x);

    await expect(aiBubble.getByText('基准值把序列分成较小和较大的两部分。')).toBeVisible();
    await expect(page.getByRole('button', { name: '暂停' })).toBeEnabled();
    await expect(questionBox).toBeEnabled();
  });

  test('automatically plays all pages in order and stops on the last page', async ({ teacherPage: page }) => {
    await installClassroomRoutes(page, 0);
    await installSpeechMock(page, (text) => (text === '回答' ? 10_000 : 40));
    await page.goto(`/#classroom-player?course_id=${courseId}&classroom_id=${classroomId}`);

    await page.getByRole('button', { name: '播放当前页' }).click();
    await expect(page.getByText('3 / 3')).toBeVisible();
    await expect(page.getByTitle('第三页：递归处理')).toBeVisible();
    await expect(page.getByRole('button', { name: '重播当前页' })).toBeEnabled();
  });
});
