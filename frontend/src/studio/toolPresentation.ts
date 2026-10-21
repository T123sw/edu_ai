const captions: Record<string, { description: string; action: string }> = {
  report: { description: '理清原理，把重点与实例连起来', action: '梳理与理解' },
  quiz: { description: '用一次练习，看看自己理解了多少', action: '练习与检验' },
  flashcard: { description: '一问一答，让核心概念更好记', action: '记忆与复习' },
  mind_map: { description: '展开知识脉络，看清概念间的联系', action: '结构与关联' },
  podcast: { description: '用音频讲解，听懂原理与应用', action: '聆听与理解' },
  scenario: { description: '进入情景，做出选择并观察后果', action: '决策与实践' },
};
export const toolPresentation = (type: string) => captions[type] || captions.report;
