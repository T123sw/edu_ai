import type { GenerationConfigDefinition } from "./types";

export type PptOutlineSlide = { id: string; title: string; keyPoints: string[]; speakerNotes: string; visualInstruction: string };
export type PptConfig = {
  deckTitle: string;
  deckSubtitle: string;
  audience: string;
  objective: string;
  slideCount: number;
  focus: string;
  style: string;
  template: "heu_academic_elegant" | "heu_academic_basic";
  outline: PptOutlineSlide[];
};

export const pptDefinition: GenerationConfigDefinition<PptConfig> = {
  resourceType: "ppt",
  title: "配置 PPT 与逐页大纲",
  description: "先填写演示目标，再用结构化字段编辑逐页大纲；不需要接触 JSON。",
  defaultConfig: () => ({
    deckTitle: "",
    deckSubtitle: "",
    audience: "本科一年级",
    objective: "理解核心概念并能解释典型现象",
    slideCount: 10,
    focus: "概念、证据与课堂互动",
    style: "图文均衡、重点清晰",
    template: "heu_academic_elegant",
    outline: [
      { id: "slide-intro", title: "问题导入", keyPoints: ["提出本节核心问题"], speakerNotes: "用一个真实情境引出主题", visualInstruction: "主题图片或简洁示意图" },
      { id: "slide-core", title: "核心概念", keyPoints: ["定义", "关键关系"], speakerNotes: "逐步解释并检查理解", visualInstruction: "概念关系图" },
      { id: "slide-summary", title: "总结与练习", keyPoints: ["回顾重点", "课堂检测"], speakerNotes: "邀请学生用自己的话总结", visualInstruction: "三点总结卡片" },
    ],
  }),
  validate: (config) => ({
    ...(config.deckTitle.trim() ? {} : { deckTitle: "请输入 PPT 标题" }),
    ...(config.slideCount >= 5 && config.slideCount <= 30 ? {} : { slideCount: "页数需为 5–30" }),
    ...(config.outline.length ? {} : { outline: "至少保留一页大纲" }),
    ...(config.outline.every((slide) => slide.title.trim()) ? {} : { outline: "每页都需要标题" }),
  }),
  serialize: ({ config }) => ({
    ppt_config: {
      deck_title: config.deckTitle.trim(),
      deck_subtitle: config.deckSubtitle.trim(),
      audience: config.audience.trim(),
      objective: config.objective.trim(),
      theme_id: config.template,
      length_option: config.slideCount <= 8 ? "short" : config.slideCount >= 15 ? "long" : "medium",
      target_slide_count: config.slideCount,
      key_points: config.focus.split(/[、，,\n]/u).map((item) => item.trim()).filter(Boolean),
      style_hint: config.style.trim(),
      special_requirements: "",
      general_requirements: config.focus.trim(),
    },
    outline: config.outline.map((slide) => ({ ...slide, keyPoints: [...slide.keyPoints] })),
  }),
};
