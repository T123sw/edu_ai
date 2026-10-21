import { resourceEvidence, type Classroom, type Message } from "./model";

export function chapterMessages(room: Classroom, chapterId: string): Message[] {
  const chapter = room.chapters.find(c => c.id === chapterId);
  return room.messages.filter(m => m.chapterId ? m.chapterId === chapterId : chapter?.resources.some(r => r.id === m.resourceId));
}

export function learningMemory(room: Classroom) {
  return room.chapters.map(chapter => {
    const evidence = chapter.resources.map(r => resourceEvidence(room, r));
    const completed = evidence.filter(e => e.completed).length;
    const answers = room.live ? [] : evidence.filter(e => e.answer !== undefined);
    const practice = chapter.resources.map(r => room.practice?.[r.id]).filter(Boolean);
    const practiceCorrect = practice.reduce((n, p) => n + (p?.correct || 0), 0);
    const practiceGraded = practice.reduce((n, p) => n + (p?.graded || 0), 0);
    const incorrect = answers.some(e => e.answer !== 1) || practiceCorrect < practiceGraded;
    const rating = room.understanding?.[chapter.id];
    const started = evidence.some(e => e.completed || e.position > 0 || e.note || e.answer !== undefined) || chapterMessages(room, chapter.id).length > 0;
    const status = rating === "review" ? "待巩固" : rating === "understood" ? "自评已理解" : incorrect ? "建议回顾" : started ? "学习中" : "未开始";
    const projection = room.learningProjection?.topics.find(t => t.topic_id === chapter.id);
    const facts = projection ? `${projection.total_core === null ? "核心要求尚未定义" : `核心资料 ${projection.completed_core}/${projection.total_core}`} · 理解尚未验证` : `学完 ${completed}/${chapter.resources.length} 份${practiceGraded ? ` · 练习 ${practiceCorrect}/${practiceGraded} 正确` : answers.length ? ` · 练习 ${answers.filter(e => e.answer === 1).length}/${answers.length} 正确` : " · 尚无练习反馈"}`;
    return { chapterId: chapter.id, title: chapter.title, status, facts };
  });
}

// The course shares recent dialogue; learning facts retain their topic attribution.
export function agentContext(room: Classroom, chapterId: string) {
  return {
    goal: room.goal,
    chapterId,
    recentMessages: room.messages.slice(-12),
    memory: learningMemory(room),
  };
}
