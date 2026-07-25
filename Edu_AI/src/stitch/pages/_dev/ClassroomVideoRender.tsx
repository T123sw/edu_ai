import { useEffect, useRef, useState } from 'react';
import type { Action, Slide as DslSlide } from '@openmaic/dsl';
import type { Slide } from '@openmaic/renderer';
import { SlidePlayer } from '../../../openmaic/SlidePlayer';
import type { LessonTimeline } from '../../../openmaic/timeline';
import {
  failVideoRenderSession,
  selectVideoRenderScene,
} from '../../../openmaic/videoRenderState';
import { getClassroom } from '../../api/classroom';
import type { ClassroomMaterial, ClassroomScene } from '../../api/types';

type RenderStatus = 'loading' | 'playing' | 'completed' | 'failed';

type RenderQuery = {
  fixture: boolean;
  courseId: string | null;
  classroomId: string | null;
  sceneIndex: number;
};

function getRenderQuery(): RenderQuery {
  const params = new URLSearchParams(window.location.hash.split('?')[1] ?? '');
  const parsedIndex = Number.parseInt(params.get('scene_index') ?? '0', 10);
  return {
    fixture: params.get('fixture') === '1',
    courseId: params.get('course_id'),
    classroomId: params.get('classroom_id'),
    sceneIndex: Number.isInteger(parsedIndex) && parsedIndex >= 0 ? parsedIndex : 0,
  };
}

function writeAscii(view: DataView, offset: number, value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function createSilentWavDataUrl(durationMs: number, sampleRate = 8000): string {
  const sampleCount = Math.ceil((durationMs / 1000) * sampleRate);
  const bytesPerSample = 2;
  const dataLength = sampleCount * bytesPerSample;
  const bytes = new Uint8Array(44 + dataLength);
  const view = new DataView(bytes.buffer);
  writeAscii(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataLength, true);
  writeAscii(view, 8, 'WAVE');
  writeAscii(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, 'data');
  view.setUint32(40, dataLength, true);

  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return `data:audio/wav;base64,${window.btoa(binary)}`;
}

function fixtureSlide(id: string, title: string, accent: string): DslSlide {
  return {
    id,
    viewportSize: 1920,
    viewportRatio: 0.5625,
    theme: {
      backgroundColor: '#f8fafc',
      themeColors: [accent],
      fontColor: '#0f172a',
      fontName: '"Microsoft YaHei", "Noto Sans SC", sans-serif',
    },
    elements: [
      {
        id: `${id}-title`,
        type: 'text',
        left: 180,
        top: 260,
        width: 1560,
        height: 210,
        rotate: 0,
        content: `<p style="font-family:Microsoft YaHei,sans-serif;font-size:88px;font-weight:800;text-align:center;color:${accent}">${title}</p>`,
        defaultFontName: 'Microsoft YaHei',
        defaultColor: accent,
      },
      {
        id: `${id}-body`,
        type: 'text',
        left: 300,
        top: 560,
        width: 1320,
        height: 130,
        rotate: 0,
        content:
          '<p style="font-family:Microsoft YaHei,sans-serif;font-size:42px;text-align:center;color:#334155">OpenMAIC 课件视频导出验收</p>',
        defaultFontName: 'Microsoft YaHei',
        defaultColor: '#334155',
      },
    ],
    background: { type: 'solid', color: '#f8fafc' },
  };
}

function createFixtureMaterial(): ClassroomMaterial {
  const narration = createSilentWavDataUrl(650);
  const scenes: ClassroomScene[] = [
    { id: 'fixture-interactive', type: 'interactive' },
    {
      id: 'fixture-slide-1',
      type: 'slide',
      content: {
        type: 'slide',
        canvas: fixtureSlide('fixture-canvas-1', '第一幕：稳定渲染', '#2563eb') as unknown as Record<
          string,
          unknown
        >,
      },
      actions: [
        { id: 'fixture-focus-1', type: 'spotlight', elementId: 'fixture-canvas-1-title' },
        {
          id: 'fixture-speech-1',
          type: 'speech',
          text: '第一幕验证中文课件、聚焦效果与配音时间线。',
          audioUrl: narration,
        },
      ],
    },
    {
      id: 'fixture-slide-2',
      type: 'slide',
      content: {
        type: 'slide',
        canvas: fixtureSlide('fixture-canvas-2', '第二幕：可重复录制', '#7c3aed') as unknown as Record<
          string,
          unknown
        >,
      },
      actions: [
        {
          id: 'fixture-speech-2',
          type: 'speech',
          text: '第二幕验证多场景分段录制与后续合并。',
          audioUrl: narration,
        },
      ],
    },
  ];
  return {
    material_id: 'fixture-video-render',
    material_type: 'classroom',
    title: '视频导出浏览器验收',
    course_id: 'fixture-course',
    scenes,
    scenes_count: scenes.length,
  };
}

export function ClassroomVideoRenderPage() {
  const [query, setQuery] = useState(getRenderQuery);
  const [material, setMaterial] = useState<ClassroomMaterial | null>(null);
  const [status, setStatus] = useState<RenderStatus>('loading');
  const [error, setError] = useState('');
  const [timeline, setTimeline] = useState<LessonTimeline | null>(null);
  const timelineRef = useRef<LessonTimeline | null>(null);

  useEffect(() => {
    const syncQuery = () => setQuery(getRenderQuery());
    window.addEventListener('hashchange', syncQuery);
    return () => window.removeEventListener('hashchange', syncQuery);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      try {
        setMaterial(null);
        setTimeline(null);
        timelineRef.current = null;
        setError('');
        setStatus('loading');
        let loaded: ClassroomMaterial;
        if (query.fixture) {
          loaded = createFixtureMaterial();
        } else if (query.courseId && query.classroomId) {
          loaded = await getClassroom(query.courseId, query.classroomId);
        } else {
          throw new Error('course_id and classroom_id are required');
        }
        if (!cancelled) {
          setMaterial(loaded);
          setStatus('playing');
        }
      } catch (reason) {
        if (!cancelled) {
          const failed = failVideoRenderSession(reason);
          setError(failed.error);
          setStatus('failed');
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [query]);

  let selected: ReturnType<typeof selectVideoRenderScene> | null = null;
  if (material) {
    try {
      selected = selectVideoRenderScene(material.scenes ?? [], query.sceneIndex);
    } catch (reason) {
      if (status !== 'failed') {
        queueMicrotask(() => {
          const failed = failVideoRenderSession(reason);
          setError(failed.error);
          setStatus('failed');
        });
      }
    }
  }

  const scene = selected?.scene;
  const slide = scene?.content?.canvas as unknown as Slide | undefined;
  const actions = (scene?.actions ?? []) as Action[];
  const serializedTimeline = timeline ? JSON.stringify(timeline) : '';

  function handleTimelineChange(nextTimeline: LessonTimeline): void {
    timelineRef.current = nextTimeline;
    setTimeline(nextTimeline);
  }

  function handleComplete(): void {
    if (timelineRef.current) {
      setTimeline(timelineRef.current);
      setStatus('completed');
    } else {
      setError('player completed without a measured timeline');
      setStatus('failed');
    }
  }

  return (
    <div
      data-video-render-root
      data-export-status={status}
      data-scene-count={selected?.sceneCount ?? 0}
      data-scene-index={selected?.renderIndex ?? query.sceneIndex}
      data-scene-id={scene?.id ?? ''}
      data-export-error={error}
      style={{
        position: 'relative',
        width: 1920,
        height: 1080,
        overflow: 'hidden',
        background: '#020617',
      }}
    >
      {slide ? (
        <SlidePlayer
          key={scene?.id}
          slide={slide}
          actions={actions}
          sceneId={scene?.id}
          onTimelineChange={handleTimelineChange}
          onComplete={handleComplete}
        />
      ) : null}
      <pre data-export-timeline hidden>
        {serializedTimeline}
      </pre>
      {status === 'failed' ? (
        <div
          role="alert"
          style={{
            display: 'grid',
            width: '100%',
            height: '100%',
            placeItems: 'center',
            color: '#fecaca',
            font: '32px sans-serif',
          }}
        >
          {error}
        </div>
      ) : null}
    </div>
  );
}
