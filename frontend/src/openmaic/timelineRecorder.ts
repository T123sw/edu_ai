import type { LessonTimeline, SceneSegment, TimelineClip } from './timeline';

interface RecordedAction {
  startedAtMs?: number;
  endedAtMs?: number;
}

function cloneTimeline(timeline: LessonTimeline): LessonTimeline {
  return structuredClone(timeline);
}

function actionKey(sceneId: string, actionId: string): string {
  return `${sceneId}\u0000${actionId}`;
}

function findClip(scene: SceneSegment, actionId: string): TimelineClip | undefined {
  return scene.clips.find((clip) => clip.actionId === actionId);
}

export class TimelineRecorder {
  private readonly working: LessonTimeline;
  private readonly recordedActions = new Map<string, RecordedAction>();
  private readonly startedScenes = new Set<string>();
  private lessonStartedAtMs: number | null = null;

  constructor(template: LessonTimeline) {
    this.working = cloneTimeline(template);
  }

  onActionStart(actionId: string, sceneId: string, timeMs: number): void {
    const scene = this.working.scenes.find((candidate) => candidate.sceneId === sceneId);
    if (!scene) return;
    const clip = findClip(scene, actionId);
    if (!clip) return;

    if (this.lessonStartedAtMs === null) this.lessonStartedAtMs = timeMs;
    if (!this.startedScenes.has(sceneId)) {
      scene.startMs = timeMs - this.lessonStartedAtMs;
      this.startedScenes.add(sceneId);
    }

    const record = this.recordedActions.get(actionKey(sceneId, actionId)) ?? {};
    record.startedAtMs = timeMs;
    this.recordedActions.set(actionKey(sceneId, actionId), record);
    clip.startMs = timeMs - (this.lessonStartedAtMs + scene.startMs);
  }

  onActionEnd(actionId: string, sceneId: string, timeMs: number): void {
    const scene = this.working.scenes.find((candidate) => candidate.sceneId === sceneId);
    if (!scene) return;
    const clip = findClip(scene, actionId);
    if (!clip) return;

    const key = actionKey(sceneId, actionId);
    const record = this.recordedActions.get(key) ?? {};
    record.endedAtMs = timeMs;
    this.recordedActions.set(key, record);

    if (clip.concurrentWith) return;
    if (record.startedAtMs === undefined) return;

    clip.durationMs = Math.max(0, timeMs - record.startedAtMs);
    clip.durationSource = 'measured';

    for (const concurrent of scene.clips) {
      if (concurrent.concurrentWith !== clip.id) continue;
      concurrent.startMs = clip.startMs;
      concurrent.durationMs = clip.durationMs;
      concurrent.durationSource = 'measured';
    }
  }

  snapshot(): LessonTimeline {
    const timeline = cloneTimeline(this.working);
    for (const scene of timeline.scenes) {
      scene.durationMs = scene.clips.reduce(
        (maximum, clip) => Math.max(maximum, clip.startMs + clip.durationMs),
        0,
      );
    }
    timeline.durationMs = timeline.scenes.reduce(
      (maximum, scene) => Math.max(maximum, scene.startMs + scene.durationMs),
      0,
    );
    return timeline;
  }
}
