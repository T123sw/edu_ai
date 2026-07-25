import {
  createDefaultRenderConfig,
  type LessonTimeline,
  type SceneSegment,
  type TimelineClip,
} from './timeline.ts';

export class TimelineValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TimelineValidationError';
  }
}

function requireNonNegativeFinite(value: number, label: string): void {
  if (!Number.isFinite(value) || value < 0) {
    throw new TimelineValidationError(`${label} must be a non-negative number`);
  }
}

function validateTrackOverlaps(scene: SceneSegment): void {
  const byTrack = new Map<string, TimelineClip[]>();
  for (const clip of scene.clips) {
    if (clip.track === 'focus' || clip.durationMs === 0) continue;
    const clips = byTrack.get(clip.track) ?? [];
    clips.push(clip);
    byTrack.set(clip.track, clips);
  }

  for (const [track, clips] of byTrack) {
    const ordered = [...clips].sort(
      (left, right) => left.startMs - right.startMs,
    );
    for (let index = 1; index < ordered.length; index += 1) {
      const previous = ordered[index - 1];
      const current = ordered[index];
      if (current.startMs < previous.startMs + previous.durationMs) {
        throw new TimelineValidationError(
          `${track} clips overlap in ${scene.sceneId}`,
        );
      }
    }
  }
}

export function validateLessonTimeline(timeline: LessonTimeline): void {
  if (!Number.isInteger(timeline.version) || timeline.version < 1) {
    throw new TimelineValidationError('timeline version must be a positive integer');
  }
  requireNonNegativeFinite(timeline.durationMs, 'timeline durationMs');

  const orderedScenes = [...timeline.scenes].sort(
    (left, right) => left.startMs - right.startMs,
  );
  for (let index = 0; index < orderedScenes.length; index += 1) {
    const scene = orderedScenes[index];
    requireNonNegativeFinite(scene.startMs, `${scene.sceneId}.startMs`);
    requireNonNegativeFinite(scene.durationMs, `${scene.sceneId}.durationMs`);
    if (
      index > 0 &&
      scene.startMs <
        orderedScenes[index - 1].startMs +
          orderedScenes[index - 1].durationMs
    ) {
      throw new TimelineValidationError(`${scene.sceneId} overlaps a prior scene`);
    }

    for (const clip of scene.clips) {
      requireNonNegativeFinite(
        clip.startMs,
        `${scene.sceneId}/${clip.actionId}.startMs`,
      );
      requireNonNegativeFinite(
        clip.durationMs,
        `${scene.sceneId}/${clip.actionId}.durationMs`,
      );
      if (clip.startMs + clip.durationMs > scene.durationMs + 0.5) {
        throw new TimelineValidationError(
          `${clip.actionId} ends after its scene`,
        );
      }
    }
    validateTrackOverlaps(scene);
  }

  const measuredDuration = orderedScenes.reduce(
    (maximum, scene) => Math.max(maximum, scene.startMs + scene.durationMs),
    0,
  );
  if (timeline.durationMs + 0.5 < measuredDuration) {
    throw new TimelineValidationError('timeline ends before its final scene');
  }
}

function srtTimestamp(timeMs: number): string {
  const rounded = Math.max(0, Math.round(timeMs));
  const milliseconds = rounded % 1000;
  const totalSeconds = Math.floor(rounded / 1000);
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutes = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);
  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')
    .concat(',', String(milliseconds).padStart(3, '0'));
}

export function timelineToSrt(timeline: LessonTimeline): string {
  validateLessonTimeline(timeline);
  const narration = timeline.scenes
    .flatMap((scene) =>
      scene.clips
        .filter(
          (clip) =>
            clip.track === 'narration' &&
            clip.durationMs > 0 &&
            typeof clip.payload.text === 'string' &&
            clip.payload.text.trim().length > 0,
        )
        .map((clip) => ({
          startMs: scene.startMs + clip.startMs,
          endMs: scene.startMs + clip.startMs + clip.durationMs,
          text: String(clip.payload.text)
            .replace(/\r\n?/g, '\n')
            .trim(),
        })),
    )
    .sort((left, right) => left.startMs - right.startMs);

  return narration
    .flatMap((entry, index) => [
      String(index + 1),
      `${srtTimestamp(entry.startMs)} --> ${srtTimestamp(entry.endMs)}`,
      entry.text,
      '',
    ])
    .join('\n');
}

export function mergeMeasuredSceneTimelines(
  lessonId: string,
  sceneTimelines: readonly LessonTimeline[],
): LessonTimeline {
  if (sceneTimelines.length === 0) {
    throw new TimelineValidationError('at least one scene timeline is required');
  }

  let cursorMs = 0;
  const scenes: SceneSegment[] = [];
  for (const sourceTimeline of sceneTimelines) {
    validateLessonTimeline(sourceTimeline);
    if (sourceTimeline.scenes.length !== 1) {
      throw new TimelineValidationError(
        'each measured input must contain exactly one scene',
      );
    }
    const scene = structuredClone(sourceTimeline.scenes[0]);
    scene.sceneIndex = scenes.length;
    scene.startMs = cursorMs;
    scenes.push(scene);
    cursorMs += scene.durationMs;
  }

  const first = sceneTimelines[0];
  const merged: LessonTimeline = {
    version: Math.max(...sceneTimelines.map((timeline) => timeline.version)),
    lessonId,
    durationMs: cursorMs,
    viewport: structuredClone(first.viewport),
    scenes,
    render: structuredClone(first.render ?? createDefaultRenderConfig()),
  };
  validateLessonTimeline(merged);
  return merged;
}
