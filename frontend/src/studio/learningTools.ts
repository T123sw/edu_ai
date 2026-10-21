import { generationRegistry, type GenerationResourceType } from '../components/generation/generationRegistry';

type Config = Record<string, unknown>;
export type StudioTool = GenerationResourceType | 'podcast' | 'scenario';
const definition = (kind: 'podcast' | 'scenario') => ({
  resourceType: kind,
  defaultConfig: (): Config => kind === 'podcast' ? { topic: '', duration_minutes: 5, focus: '' } : { topic: '', difficulty: 'medium', setting: '' },
  validate: (config: Config) => String(config.topic || '').trim() ? {} : { topic: '请输入主题' },
  serialize: ({ config }: { config: Config }) => ({ ...config, topic: String(config.topic || '').trim() }),
});

export const studioRegistry: { resourceType: StudioTool; canonicalType: string; label: string; definition: object }[] = [
  ...generationRegistry.filter(item => ['report', 'quiz', 'flashcard', 'mind_map'].includes(item.resourceType)),
  { resourceType: 'podcast', canonicalType: 'podcast', label: '播客', definition: definition('podcast') },
  { resourceType: 'scenario', canonicalType: 'scenario', label: '情景案例', definition: definition('scenario') },
];
