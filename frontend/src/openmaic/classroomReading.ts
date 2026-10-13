import type { Action } from '@openmaic/dsl';
import type { ActionEffectsState } from './actionEngine';
import type { PagePlaybackSnapshot } from './pagePlaybackController';

export type LecturePosition = {
  scene_id: string;
  action_id: string;
  speech_action_id?: string;
  sentence_index?: number;
  sentence_alignment?: 'estimated' | 'sentence';
  speech_completed: boolean;
  highlighted_element_ids: string[];
};
export type ClassroomReadingContext = { status: PagePlaybackSnapshot['status']; lecture?: LecturePosition };

/** Keeps the last spoken position even when pause/navigation disposes the player. */
export class LecturePositionTracker {
  private position?: LecturePosition;
  private muted = false;
  private lastEmission = '';
  constructor(private readonly sceneId: string, private readonly emit: (position: LecturePosition) => void) {}

  start(action: Action) {
    if (this.muted) return;
    this.position = { ...this.position, scene_id: this.sceneId, action_id: action.id,
      speech_completed: this.position?.speech_completed ?? false,
      highlighted_element_ids: this.position?.highlighted_element_ids ?? [] };
    if (action.type === 'speech') {
      this.position.speech_action_id = action.id;
      this.position.speech_completed = false;
      delete this.position.sentence_index;
      delete this.position.sentence_alignment;
    }
    this.publish();
  }

  end(action: Action) {
    if (!this.muted && this.position && action.type === 'speech') {
      this.position.speech_completed = true;
      this.publish();
    }
  }

  sentence(actionId: string, index: number, alignment: 'estimated' | 'sentence') {
    if (this.muted || this.position?.speech_action_id !== actionId) return;
    this.position.sentence_index = index;
    this.position.sentence_alignment = alignment;
    this.publish();
  }

  effects(effects: ActionEffectsState) {
    if (this.muted || !this.position) return;
    this.position.highlighted_element_ids = [...new Set([effects.spotlight?.elementId, effects.laser?.elementId].filter((id): id is string => !!id))];
    this.publish();
  }

  /** Remain frozen through asynchronous cancellation callbacks, until resumed. */
  freeze() { this.muted = true; }
  resume() { this.muted = false; }
  restart() { this.position = undefined; this.lastEmission = ''; this.muted = false; }

  private publish() {
    if (!this.position || this.muted) return;
    const serialized = JSON.stringify(this.position);
    if (serialized === this.lastEmission) return;
    this.lastEmission = serialized;
    this.emit(JSON.parse(serialized) as LecturePosition);
  }
}
