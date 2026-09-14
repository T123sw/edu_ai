// Local interaction adapter. Replace this boundary with server operations at integration.
export type ResourceKind = "report" | "video" | "slides" | "quiz";
export const kindLabel: Record<ResourceKind, string> = {
  report: "学习报告",
  video: "视频讲解",
  slides: "演示课件",
  quiz: "巩固练习",
};
export type LearningResource = {
  id: string;
  title: string;
  topic: string;
  kind: ResourceKind;
  ready: boolean;
  minutes: number;
  createdAt: number;
};
export type Chapter = {
  id: string;
  title: string;
  resources: LearningResource[];
};
export type Evidence = {
  completed: boolean;
  position: number;
  note: string;
  answer?: number;
};
export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  resourceId: string;
  resourceTitle: string;
};
export type Classroom = {
  id: string;
  title: string;
  goal: string;
  tone: string;
  chapters: Chapter[];
  selectedId: string;
  progress: Record<string, Evidence>;
  messages: Message[];
  updatedAt: number;
  publisher?: string;
  sourceId?: string;
};
export type GenerationJob = {
  id: string;
  title: string;
  roomId?: string;
  resource?: LearningResource;
  status: "running" | "cancelled" | "done";
  elapsed: number;
  duration: number;
};
export type LearningState = {
  version: 1;
  rooms: Classroom[];
  resources: LearningResource[];
  jobs: GenerationJob[];
};
export const uid = (): string => {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // LAN HTTP previews are not secure contexts: randomUUID may be unavailable.
  return `local-${Array.from(crypto.getRandomValues(new Uint32Array(4)), (n) => n.toString(16).padStart(8, "0")).join("")}`;
};
export const allResources = (room: Classroom) =>
  room.chapters.flatMap((c) => c.resources);
export const completion = (room: Classroom) =>
  allResources(room).filter((r) => room.progress[r.id]?.completed).length;
export const emptyEvidence = (): Evidence => ({
  completed: false,
  position: 0,
  note: "",
});

const outlines = {
  agent: [
    "Agent 基础概念",
    "ReAct：推理与行动",
    "工具调用与 MCP",
    "构建你的第一个 Agent",
  ],
  python: [
    "Python 与编程思维",
    "变量、容器与控制流",
    "函数与模块",
    "完成一个自动化脚本",
  ],
  design: [
    "理解设计与用户",
    "视觉层级与信息组织",
    "交互与反馈",
    "从想法到作品",
  ],
};

export function createClassroom(
  requirement: string,
  ready = false,
  id: string = uid(),
): Classroom {
  const goal = requirement.trim();
  const topic = /agent|智能体|mcp|react/i.test(goal)
    ? "Agent"
    : /python|编程/i.test(goal)
      ? "Python"
      : /设计/.test(goal)
        ? "设计"
        : goal.split(/[，。！？,!?\n]/)[0].slice(0, 24);
  const names =
    topic === "Agent"
      ? outlines.agent
      : topic === "Python"
        ? outlines.python
        : topic === "设计"
          ? outlines.design
          : [
              `${topic}：基础概念`,
              "核心方法与原理",
              "案例与实际应用",
              "综合实践与回顾",
            ];
  const chapters = names.map(
    (title, i): Chapter => ({
      id: `${id}-chapter-${i}`,
      title,
      resources: (
        ["video", "report", ...(i === 3 ? ["quiz"] : [])] as ResourceKind[]
      ).map((kind) => ({
        id: `${id}-${i}-${kind}`,
        title:
          kind === "video"
            ? `${title} · 讲解`
            : kind === "quiz"
              ? "学习检查"
              : `${title} · 学习笔记`,
        topic: title,
        kind,
        ready,
        minutes: kind === "video" ? 8 + i * 2 : 5 + i,
        createdAt: Date.now(),
      })),
    }),
  );
  return {
    id,
    title:
      topic === "Agent"
        ? "从零开始，理解 Agent"
        : topic === "Python"
          ? "Python 学习之旅"
          : `${topic}学习课堂`,
    goal,
    tone: topic === "Python" ? "mint" : topic === "设计" ? "peach" : "violet",
    chapters,
    selectedId: chapters[0].resources[0].id,
    progress: {},
    messages: [],
    updatedAt: Date.now(),
  };
}

export function seedState(): LearningState {
  const room = createClassroom(
    "我会 Python，希望系统学习 Agent，独立开发一个应用。",
    true,
    "sample-agent",
  );
  const resources = allResources(room);
  room.progress[resources[0].id] = {
    ...emptyEvidence(),
    completed: true,
    position: 36,
  };
  room.selectedId = resources[1].id;
  const python = createClassroom(
    "用 Python 处理数据，完成一个自动化脚本。",
    true,
    "sample-python",
  );
  python.updatedAt -= 86400000;
  return { version: 1, rooms: [room, python], resources: [], jobs: [] };
}

export function sharedSeeds(): Classroom[] {
  return [
    {
      ...createClassroom("Agent 入门：从原理到实践", true, "shared-agent"),
      title: "Agent 入门：从原理到实践",
      publisher: "林老师",
    },
    {
      ...createClassroom("Python 数据分析与自动化", true, "shared-python"),
      title: "用 Python 打开数据世界",
      publisher: "陈老师",
    },
    {
      ...createClassroom("设计基础与交互思维", true, "shared-design"),
      title: "每个人都能学会的设计思维",
      publisher: "周老师",
    },
  ];
}

export function startShared(
  state: LearningState,
  template: Classroom,
): [LearningState, Classroom] {
  const existing = state.rooms.find((r) => r.sourceId === template.id);
  if (existing) return [state, existing];
  const room: Classroom = {
    ...structuredClone(template),
    id: uid(),
    sourceId: template.id,
    progress: {},
    messages: [],
    selectedId: allResources(template)[0].id,
    updatedAt: Date.now(),
  };
  return [{ ...state, rooms: [room, ...state.rooms] }, room];
}

export function addClassroom(
  state: LearningState,
  room: Classroom,
): LearningState {
  return {
    ...state,
    rooms: [room, ...state.rooms],
    jobs: [
      {
        id: uid(),
        roomId: room.id,
        title: room.title,
        status: "running",
        elapsed: 0,
        duration: 16000,
      },
      ...state.jobs,
    ],
  };
}

export function updateRoom(
  state: LearningState,
  id: string,
  update: (room: Classroom) => Classroom,
): LearningState {
  return {
    ...state,
    rooms: state.rooms.map((r) => (r.id === id ? update(r) : r)),
  };
}

export function updateEvidence(
  state: LearningState,
  roomId: string,
  resourceId: string,
  patch: Partial<Evidence>,
): LearningState {
  return updateRoom(state, roomId, (r) => ({
    ...r,
    updatedAt: Date.now(),
    progress: {
      ...r.progress,
      [resourceId]: { ...emptyEvidence(), ...r.progress[resourceId], ...patch },
    },
  }));
}

export function advanceJobs(
  state: LearningState,
  delta: number,
): LearningState {
  if (!state.jobs.some((j) => j.status === "running")) return state;
  let next = { ...state, resources: [...state.resources] };
  const jobs = state.jobs.map((job): GenerationJob => {
    if (job.status !== "running") return job;
    const elapsed = Math.min(job.duration, job.elapsed + delta);
    if (job.roomId)
      next = updateRoom(next, job.roomId, (room) => {
        const count = Math.floor(
          (elapsed / job.duration) * allResources(room).length,
        );
        let i = 0;
        return {
          ...room,
          chapters: room.chapters.map((chapter) => ({
            ...chapter,
            resources: chapter.resources.map((r) => {
              i += 1;
              return { ...r, ready: r.ready || i <= count };
            }),
          })),
        };
      });
    if (
      elapsed === job.duration &&
      job.resource &&
      !next.resources.some((r) => r.id === job.resource!.id)
    )
      next.resources.unshift({ ...job.resource, ready: true });
    return {
      ...job,
      elapsed,
      status: elapsed === job.duration ? "done" : "running",
    };
  });
  return { ...next, jobs };
}

export function jobAction(
  state: LearningState,
  id: string,
  action: "cancel" | "retry",
): LearningState {
  return {
    ...state,
    jobs: state.jobs.map((j) =>
      j.id === id && j.status !== "done"
        ? { ...j, status: action === "cancel" ? "cancelled" : "running" }
        : j,
    ),
  };
}

export function createStudioJob(
  title: string,
  kind: ResourceKind,
): GenerationJob {
  return {
    id: uid(),
    title: title.trim(),
    status: "running",
    elapsed: 0,
    duration: 6000,
    resource: {
      id: uid(),
      title: title.trim(),
      topic: title.trim(),
      kind,
      ready: false,
      minutes: 6,
      createdAt: Date.now(),
    },
  };
}

export function agentReply(
  room: Classroom,
  resource: LearningResource,
  question: string,
): string {
  const e = room.progress[resource.id];
  const location = `你正在学习「${resource.topic}」，本课堂已标记完成 ${completion(room)} / ${allResources(room).length} 份资源。`;
  if (/下一|接下来|进度/.test(question))
    return `${location}\n${e?.completed ? "这份内容已完成，可以点击下方的“下一份资源”继续。" : "这份内容还未标记完成。可以先说说你对核心概念的理解，再决定继续还是回顾。"}`;
  if (/不懂|例子|解释/.test(question))
    return `${location}\n我们可以从一个具体任务开始：让助手整理一份旅行计划。模型负责理解目标，工具负责查询外部信息，Agent 把判断与行动组织起来。试着想一想：只回答一个问题，和持续完成一个目标，有什么区别？\n这是预设的 Agent 教学示例；真实的主题问答将在接口联调时接入。`;
  if (e?.answer !== undefined)
    return `${location}\n刚才的示例检查${e.answer === 1 ? "选择正确" : "还需要回顾"}。这只是当前题目的反馈，我们可以继续用一个新例子检查理解。`;
  return `${location}\n我记下了你的问题：「${question}」。你可以告诉我具体卡在哪个概念，或先用自己的话总结这一部分。\n当前为本地对话演示，尚未调用模型。`;
}
