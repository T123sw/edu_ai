import type { Projection } from '../liveLearning/learningState';
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
  minutesBasis?: 'estimated' | 'measured' | 'unknown';
  createdAt: number;
  courseId?: string;
  chapterId?: string;
  version?: number;
  pinned?: boolean;
  sourceResourceId?: string;
  content?: string;
  live?: boolean;
  remote?: { materialType: string; materialId: string; courseId: string; version: number; visibility: string };
};
export function resourceDurationLabel(resource: LearningResource): string {
  if (resource.minutesBasis === 'unknown' || resource.minutes <= 0) return '时长待估';
  return `${resource.minutesBasis === 'measured' ? '' : '约 '}${resource.minutes} 分钟`;
}

export type Chapter = {
  id: string;
  title: string;
  resources: LearningResource[];
  generationState?: 'queued' | 'generating' | 'ready' | 'failed' | 'stopped';
  pendingResourceTypes?: string[];
};
export type Evidence = {
  completed: boolean;
  locator?: import('../liveLearning/readingContext').Locator;
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
  chapterId?: string;
  kind?: string;
  position?: number;
  sessionId?: string;
  answerResult?: { citations: ({ citation_id: string; title?: string } & import('../liveLearning/citationNavigation').Citation)[] };
};
export type Classroom = {
  preparationDelivery?: { state: 'complete' | 'partial'; preparationId: string; availableResources: number;
    status?: string | null;
    pending: { title: string; resourceTypes: string[] }[] };
  manifestRef?: { manifest_id: string; version: number };
  routeVersion?: number;
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
  understanding?: Record<string, "review" | "understood">;
  live?: boolean;
  agentRuntime?: boolean;
  enrichmentEnabled?: boolean;
  preparationEnabled?: boolean;
  progressPersistence?: boolean;
  progressOwner?: string;
  learningProjection?: Projection;
  sessionPersistence?: boolean;
  sessionOwner?: string;
  canPublish?: boolean;
  practice?: Record<string, { correct: number; graded: number }>;
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
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};
export const allResources = (room: Classroom) =>
  room.chapters.flatMap((c) => c.resources);
export const completion = (room: Classroom) =>
  allResources(room).filter((r) => resourceEvidence(room, r).completed).length;
export function resourceEvidence(room: Classroom, resource: LearningResource): Evidence {
  const legacy = room.progress[resource.id] || emptyEvidence();
  if (!room.progressPersistence || !resource.remote) return legacy;
  const ref = resource.remote;
  const state = room.learningProjection?.resources.find(s => s.resource_ref.course_id === ref.courseId && s.resource_ref.material_type === ref.materialType && s.resource_ref.material_id === ref.materialId && s.resource_ref.version === ref.version);
  return { note: legacy.note, completed: state?.completed || false, locator: state?.locator || undefined,
    position: state?.locator?.kind === 'document' ? state.locator.scroll_top : state?.locator?.kind === 'hyperframes' ? state.locator.seconds : 0 };
}
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

export function seedState(showcase = false): LearningState {
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
  const state: LearningState = {
    version: 1,
    rooms: [room, python],
    resources: [],
    jobs: [],
  };
  if (!showcase) return state;
  const design = createClassroom(
    "培养设计思维，完成一个学习产品的交互原型。",
    true,
    "sample-design",
  );
  design.updatedAt -= 2 * 86400000;
  state.rooms.push(design);
  const examples: [ResourceKind, string][] = [
    ["report", "Agent 入门：概念、架构与应用场景"],
    ["video", "ReAct：从推理到工具调用"],
    ["slides", "Python 数据分析学习路线"],
    ["quiz", "自主学习方法检查"],
  ];
  state.resources = examples.map(([kind, title], i) => ({
    id: `showcase-${kind}`,
    title,
    topic: title,
    kind,
    ready: true,
    minutes: 6 + i,
    createdAt: Date.now() - (i + 1) * 3600000,
  }));
  state.jobs = state.resources.map((resource) => ({
    id: `showcase-job-${resource.kind}`,
    title: resource.title,
    resource,
    status: "done",
    elapsed: 6000,
    duration: 6000,
  }));
  room.progress[resources[1].id] = {
    ...emptyEvidence(),
    note: "Agent 围绕目标组织推理与行动；工具提供与外部环境交互的能力。",
  };
  room.messages = [
    {
      id: "showcase-welcome",
      role: "assistant",
      text: "上次你已完成第一份视频讲解。现在可以阅读这份学习报告，试着用自己的话解释 Agent 与普通问答的区别。这是一条静态示例对话。",
      resourceId: resources[1].id,
      resourceTitle: resources[1].topic,
    },
  ];
  return state;
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
    understanding: {},
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
