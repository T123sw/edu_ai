import type { Action } from '@openmaic/dsl';

export type TimelineDurationSource = 'measured' | 'probed' | 'fixed' | 'media';
export type TimelineTrack = 'narration' | 'focus' | 'visual' | 'media' | 'transition';
export type TimelineActionType = Exclude<Action['type'], 'discussion'> | 'transition';

export interface RenderConfig {
  fps: number;
  resolution: { width: number; height: number };
  codec: 'h264';
  container: 'mp4';
  audioMix: {
    narrationGain: number;
    duckOnClipAudio: boolean;
    clipAudio: 'mute' | 'keep';
  };
  captions: 'none' | 'sidecar-srt' | 'burn-in';
  seed?: number;
}

export interface TimelineClip {
  id: string;
  actionId: string;
  type: TimelineActionType;
  track: TimelineTrack;
  startMs: number;
  durationMs: number;
  durationSource: TimelineDurationSource;
  payload: Record<string, unknown>;
  concurrentWith?: string;
}

export interface SceneSegment {
  sceneId: string;
  sceneIndex: number;
  startMs: number;
  durationMs: number;
  slideRef: string;
  clips: TimelineClip[];
}

export interface LessonTimeline {
  version: number;
  lessonId: string;
  durationMs: number;
  viewport: { width: number; height: number; ratio: number };
  scenes: SceneSegment[];
  render?: RenderConfig;
}

export interface TimelineSourceScene {
  id: string;
  order: number;
  slideRef?: string;
  actions?: readonly Action[];
}

export interface CompileLessonTimelineInput {
  lessonId: string;
  scenes: readonly TimelineSourceScene[];
  viewport?: { width: number; height: number; ratio: number };
  actionDurationsMs?: Readonly<Record<string, number>>;
  orphanFocusDurationMs?: number;
}

const DEFAULT_ORPHAN_FOCUS_DURATION_MS = 5000;
const DEFAULT_SYNC_DURATION_MS = 1000;

const DEFAULT_VIEWPORT = {
  width: 1920,
  height: 1080,
  ratio: 0.5625,
} as const;

function createRenderConfig(): RenderConfig {
  return {
    fps: 30,
    resolution: { width: 1920, height: 1080 },
    codec: 'h264',
    container: 'mp4',
    audioMix: {
      narrationGain: 1,
      duckOnClipAudio: false,
      clipAudio: 'mute',
    },
    captions: 'sidecar-srt',
  };
}

function actionPayload(action: Action): Record<string, unknown> {
  const { id: _id, type: _type, ...payload } = action;
  return { ...payload };
}

function trackFor(action: Exclude<Action, { type: 'discussion' }>): TimelineTrack {
  if (action.type === 'speech') return 'narration';
  if (action.type === 'spotlight' || action.type === 'laser') return 'focus';
  if (action.type === 'play_video') return 'media';
  return 'visual';
}

function estimatedSpeechDurationMs(action: Extract<Action, { type: 'speech' }>): number {
  const text = action.text.trim();
  const cjkCount = (text.match(/[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯]/g) || []).length;
  const rawDuration =
    cjkCount > text.length * 0.3
      ? Math.max(2000, text.length * 150)
      : Math.max(2000, text.split(/\s+/).filter(Boolean).length * 240);
  const speed = action.speed && action.speed > 0 ? action.speed : 1;
  return Math.round(rawDuration / speed);
}

function durationFor(action: Exclude<Action, { type: 'discussion' }>, durations: Readonly<Record<string, number>>): number {
  const supplied = durations[action.id];
  if (Number.isFinite(supplied) && supplied >= 0) return supplied;
  if (action.type === 'speech') return estimatedSpeechDurationMs(action);
  return DEFAULT_SYNC_DURATION_MS;
}

function isFocusAction(action: Action): action is Extract<Action, { type: 'spotlight' | 'laser' }> {
  return action.type === 'spotlight' || action.type === 'laser';
}

function compileScene(
  source: TimelineSourceScene,
  sceneIndex: number,
  startMs: number,
  durations: Readonly<Record<string, number>>,
  orphanFocusDurationMs: number,
): SceneSegment {
  const clips: TimelineClip[] = [];
  const pendingFocus: TimelineClip[] = [];
  let cursorMs = 0;

  for (const action of source.actions ?? []) {
    if (action.type === 'discussion') continue;

    if (isFocusAction(action)) {
      const focusClip: TimelineClip = {
        id: `${action.id}:clip`,
        actionId: action.id,
        type: action.type,
        track: 'focus',
        startMs: cursorMs,
        durationMs: orphanFocusDurationMs,
        durationSource: 'fixed',
        payload: actionPayload(action),
      };
      clips.push(focusClip);
      pendingFocus.push(focusClip);
      continue;
    }

    const durationMs = durationFor(action, durations);
    const clip: TimelineClip = {
      id: `${action.id}:clip`,
      actionId: action.id,
      type: action.type,
      track: trackFor(action),
      startMs: cursorMs,
      durationMs,
      durationSource: action.type === 'play_video' ? 'media' : 'fixed',
      payload: actionPayload(action),
    };

    if (action.type === 'speech' && pendingFocus.length > 0) {
      for (const focusClip of pendingFocus) {
        focusClip.startMs = cursorMs;
        focusClip.durationMs = durationMs;
        focusClip.concurrentWith = clip.id;
      }
      pendingFocus.length = 0;
    }

    clips.push(clip);
    cursorMs += durationMs;
  }

  const durationMs = clips.reduce(
    (maximum, clip) => Math.max(maximum, clip.startMs + clip.durationMs),
    cursorMs,
  );

  return {
    sceneId: source.id,
    sceneIndex,
    startMs,
    durationMs,
    slideRef: source.slideRef ?? source.id,
    clips,
  };
}

export function compileLessonTimeline(input: CompileLessonTimelineInput): LessonTimeline {
  const durations = input.actionDurationsMs ?? {};
  const orphanFocusDurationMs = input.orphanFocusDurationMs ?? DEFAULT_ORPHAN_FOCUS_DURATION_MS;
  const orderedScenes = input.scenes
    .map((source, originalIndex) => ({ source, originalIndex }))
    .sort((left, right) => left.source.order - right.source.order || left.originalIndex - right.originalIndex);

  let lessonCursorMs = 0;
  const scenes = orderedScenes.map(({ source }, sceneIndex) => {
    const segment = compileScene(
      source,
      sceneIndex,
      lessonCursorMs,
      durations,
      orphanFocusDurationMs,
    );
    lessonCursorMs += segment.durationMs;
    return segment;
  });

  return {
    version: 1,
    lessonId: input.lessonId,
    durationMs: lessonCursorMs,
    viewport: { ...(input.viewport ?? DEFAULT_VIEWPORT) },
    scenes,
    render: createRenderConfig(),
  };
}
