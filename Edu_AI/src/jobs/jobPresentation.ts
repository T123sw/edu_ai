const JOB_KIND_LABELS: Record<string, string> = {
  generate_classroom: "AI 课堂生成",
  render_video: "课堂视频导出",
  generate_report: "报告生成",
  generate_lesson_plan: "教案生成",
  generate_blog: "教学博客生成",
  generate_quiz: "习题生成",
  generate_ppt: "PPT 生成",
  generate_flashcard: "闪卡生成",
  generate_graph: "思维导图生成",
  generate_game: "小游戏生成",
  parse_document: "文档解析",
  build_knowledge_index: "知识库索引",
};

export function jobKindLabel(kind: string): string {
  return JOB_KIND_LABELS[kind] ?? "后台任务";
}
