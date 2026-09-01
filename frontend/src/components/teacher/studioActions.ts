export const TEACHER_STUDIO_ACTION_ORDER = [
  "report",
  "lesson_plan",
  "blog",
  "quiz",
  "flashcard",
  "graph",
  "game",
] as const;

export type TeacherStudioActionType =
  (typeof TEACHER_STUDIO_ACTION_ORDER)[number];

export type TeacherStudioAction = {
  type: TeacherStudioActionType;
  title: string;
  description: string;
  color: string;
};

export const TEACHER_STUDIO_ACTIONS: readonly TeacherStudioAction[] = [
  {
    type: "report",
    title: "报告",
    description: "将资料与课堂重点整理为结构化文稿。",
    color: "#d6a83d",
  },
  {
    type: "lesson_plan",
    title: "教案",
    description: "生成可直接修改和复用的教学流程。",
    color: "#7c8cf8",
  },
  {
    type: "blog",
    title: "教学博客",
    description: "把课堂内容沉淀为可分享的长文。",
    color: "#f07d73",
  },
  {
    type: "quiz",
    title: "习题",
    description: "围绕当前知识点生成课堂练习。",
    color: "#4a8df5",
  },
  {
    type: "flashcard",
    title: "闪卡",
    description: "提炼知识点，生成便于复习的卡片。",
    color: "#a855f7",
  },
  {
    type: "graph",
    title: "思维导图",
    description: "提取主干知识与概念之间的关系。",
    color: "#e25aa6",
  },
  {
    type: "game",
    title: "小游戏",
    description: "将资料转为可预览的课堂互动游戏。",
    color: "#2f8f6b",
  },
] as const;
