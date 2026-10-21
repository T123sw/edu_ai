import { describe, it, expect } from 'vitest';
import {
  generatePreparationClassroom,
  type NativeState,
} from '@/lib/server/preparation-generation';

const outline = {
  id: 'o1',
  type: 'slide',
  title: '划分示例',
  description: '解释不变量',
  keyPoints: ['不变量'],
  order: 0,
};
const outlineReply = JSON.stringify({
  languageDirective: '中文',
  courseTitle: '快速排序',
  outlines: [outline],
});
const slideReply = JSON.stringify({
  elements: [
    {
      id: 'text1',
      type: 'text',
      left: 40,
      top: 40,
      width: 900,
      height: 80,
      content: '<p>比较后保持左侧不大于基准。</p>',
      rotate: 0,
      defaultFontName: 'sans-serif',
      defaultColor: '#111111',
    },
  ],
});
const actionReply = JSON.stringify([{ type: 'speech', text: '每步保持已划分区间的不变量。' }]);
const input = {
  resourceId: 'r1',
  title: '排序',
  requirement: '先例后理',
  researchContext: 'SOURCE_SENTINEL',
};

describe('native preparation pipeline', () => {
  it('generates all 30 planned pages without the previous implicit 24-page cap', async () => {
    const outlines = Array.from({ length: 30 }, (_, i) => ({ ...outline, id: `o${i}`, order: i }));
    let calls = 0;
    const result = await generatePreparationClassroom(input, {
      aiCall: async (system) => {
        expect(system).not.toContain('最多 24 个场景');
        calls++;
        if (calls === 1) return JSON.stringify({ languageDirective: '中文', outlines });
        return calls % 2 === 0 ? slideReply : actionReply;
      },
      checkpoint: async () => {},
    });
    expect(result.scenes).toHaveLength(30);
    expect(calls).toBe(61);
  });
  it('runs real upstream outline, slide and action generators; persists intermediate native content', async () => {
    const calls: string[][] = [];
    const snapshots: NativeState[] = [];
    const replies = [outlineReply, slideReply, actionReply];
    const result = await generatePreparationClassroom(input, {
      aiCall: async (system, user) => {
        calls.push([system, user]);
        return replies.shift()!;
      },
      checkpoint: async (state) => {
        snapshots.push(structuredClone(state));
      },
    });
    expect(calls).toHaveLength(3);
    for (const [, user] of calls) {
      expect(user.split(input.researchContext)).toHaveLength(2);
      expect(user.split(input.requirement)).toHaveLength(2);
    }
    expect(
      calls.every(
        ([system, user]) =>
          system.includes('禁止 PBL') &&
          user.includes('SOURCE_SENTINEL') &&
          user.includes('先例后理'),
      ),
    ).toBe(true);
    expect(result.scenes[0].content.type).toBe('slide');
    expect(result.scenes[0].actions!.some((a) => a.type === 'speech')).toBe(true);
    expect(snapshots[1].pendingContent).toBeDefined();
    expect(snapshots.at(-1)!.pendingContent).toBeUndefined();
  });
  it('resumes after content without paying for outline or content again', async () => {
    let saved: NativeState | undefined;
    const replies = [outlineReply, slideReply];
    await expect(
      generatePreparationClassroom(input, {
        aiCall: async () => {
          if (!replies.length) throw new Error('provider interrupted');
          return replies.shift()!;
        },
        checkpoint: async (state) => {
          saved = structuredClone(state);
        },
      }),
    ).rejects.toThrow('provider interrupted');
    let calls = 0;
    const result = await generatePreparationClassroom(
      { ...input, state: saved },
      {
        aiCall: async () => {
          calls++;
          return actionReply;
        },
        checkpoint: async () => {},
      },
    );
    expect(calls).toBe(1);
    expect(result.scenes).toHaveLength(1);
  });
  it('rejects PBL before running its generator', async () => {
    await expect(
      generatePreparationClassroom(input, {
        aiCall: async () =>
          JSON.stringify({
            languageDirective: '中文',
            outlines: [{ ...outline, type: 'pbl' }],
          }),
        checkpoint: async () => {},
      }),
    ).rejects.toThrow('policy');
  });
  it('does not silently deliver a partial classroom', async () => {
    const replies = [outlineReply, 'null'];
    await expect(
      generatePreparationClassroom(input, {
        aiCall: async () => replies.shift()!,
        checkpoint: async () => {},
      }),
    ).rejects.toThrow();
  });
});

it('repairs only the rejected page through native generators and preserves neighboring pages and scene IDs', async () => {
  const replies = [
    JSON.stringify({
      languageDirective: '中文',
      outlines: [outline, { ...outline, id: 'o2', order: 1 }],
    }),
    slideReply,
    actionReply,
    slideReply,
    actionReply,
  ];
  const original = await generatePreparationClassroom(input, {
    aiCall: async () => replies.shift()!,
    checkpoint: async () => {},
  });
  const baseline = structuredClone(original);
  const calls: string[] = [];
  const fixedReplies = [slideReply, actionReply];
  const repaired = await generatePreparationClassroom(
    { ...input, baseline, repairSceneIds: [baseline.scenes[1].id], repairFeedback: ['修正第二页'] },
    {
      aiCall: async (_system, user) => {
        calls.push(user);
        return fixedReplies.shift()!;
      },
      checkpoint: async () => {},
    },
  );
  expect(calls).toHaveLength(2);
  expect(repaired.scenes).toHaveLength(2);
  expect(repaired.scenes[0]).toEqual(original.scenes[0]);
  expect(repaired.scenes[1].id).toBe(original.scenes[1].id);
});

it('native quiz narration cannot disclose answer/analysis before submission', async () => {
  const { generateSceneActions } = await import('@/lib/generation/scene-generator');
  const question = { id: 'q1', type: 'single' as const, question: '哪个结果正确？',
    options: [{ value: 'A', label: '1' }, { value: 'B', label: '2' }], answer: ['B'], analysis: '答案为2' };
  const actions = await generateSceneActions({ ...outline, type: 'quiz' }, { questions: [question] },
    async () => { throw new Error('Question-only narration needs no model call'); }, { quizNarration: 'question-only' });
  expect(actions).toHaveLength(1);
  expect(actions[0]).toMatchObject({ type: 'speech', text: question.question });
  expect(JSON.stringify(actions)).not.toContain(question.analysis);
});
