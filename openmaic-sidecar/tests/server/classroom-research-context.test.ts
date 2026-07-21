import { describe, expect, it } from 'vitest';
import { buildGenerateClassroomInput } from '@/app/api/generate-classroom/route';
import {
  mergeResearchContexts,
  type GenerateClassroomInput,
} from '@/lib/server/classroom-generation';

describe('generate-classroom researchContext route input', () => {
  it('forwards a non-empty external research context', () => {
    const rawBody = {
      requirement: 'Teach binary search',
      researchContext: 'RAG: binary search halves the interval.',
    } as Partial<GenerateClassroomInput> & { researchContext?: string };

    expect(buildGenerateClassroomInput(rawBody)).toMatchObject({
      requirement: 'Teach binary search',
      researchContext: 'RAG: binary search halves the interval.',
    });
  });

  it('omits an empty external research context', () => {
    const rawBody = {
      requirement: 'Teach binary search',
      researchContext: '',
    } as Partial<GenerateClassroomInput> & { researchContext?: string };

    expect(buildGenerateClassroomInput(rawBody)).not.toHaveProperty('researchContext');
  });
});

describe('generate-classroom research context merge', () => {
  it('appends injected context after web context', () => {
    expect(mergeResearchContexts('WEB: current source', 'RAG: course source')).toBe(
      'WEB: current source\n\nRAG: course source',
    );
  });

  it('keeps web context when injected context is absent', () => {
    expect(mergeResearchContexts('WEB: current source', undefined)).toBe('WEB: current source');
  });

  it('keeps injected context when web context is absent', () => {
    expect(mergeResearchContexts(undefined, 'RAG: course source')).toBe('RAG: course source');
  });

  it('returns undefined when both contexts are absent', () => {
    expect(mergeResearchContexts(undefined, undefined)).toBeUndefined();
  });
});
