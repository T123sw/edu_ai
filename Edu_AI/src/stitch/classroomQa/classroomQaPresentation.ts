import type { ClassroomQaState } from './classroomQaState';

export type ClassroomQaPresentation = {
  canSubmit: boolean;
  isBusy: boolean;
  statusText: string;
};

export function toClassroomQaPresentation(
  state: ClassroomQaState,
): ClassroomQaPresentation {
  const statusByPhase = {
    ready: '可以输入问题，发送时会暂停课堂。',
    submitting: 'AI 教师正在结合当前课堂内容思考…',
    loading_audio: '回答已生成，正在准备语音…',
    playing_answer: 'AI 教师正在回答。',
    resuming: '正在继续刚才的课堂。',
    error: state.error || '课堂问答暂时失败。',
  } satisfies Record<ClassroomQaState['phase'], string>;
  return {
    canSubmit: state.phase === 'ready' && state.activeTurn === null,
    isBusy: ['submitting', 'loading_audio', 'playing_answer', 'resuming'].includes(
      state.phase,
    ),
    statusText: statusByPhase[state.phase],
  };
}
