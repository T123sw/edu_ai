export type LearningModule = 'classroom' | 'practice' | 'exam';

export const moduleIdentity = {
  classroom: {
    eyebrow: '为好奇心，留一页空白', first: '让好奇，', second: '成为你的下一堂课。',
  },
  practice: {
    eyebrow: '把一个想法，放进实验里', first: '动手试，', second: '让原理变得看得见。',
  },
  exam: {
    eyebrow: '给每一份努力，一次检验', first: '认真答，', second: '看见自己的进步。',
  },
} as const;
