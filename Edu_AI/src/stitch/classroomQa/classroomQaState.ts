import type { ClassroomQaTurn } from '../api/types';

export type ClassroomQaPhase =
  | 'closed'
  | 'drafting'
  | 'submitting'
  | 'loading_audio'
  | 'playing_answer'
  | 'resuming'
  | 'error';

export type ClassroomQaActiveTurn = {
  clientTurnId: string;
  question: string;
  turn: ClassroomQaTurn | null;
};

export type ClassroomQaState = {
  phase: ClassroomQaPhase;
  isOpen: boolean;
  turns: ClassroomQaTurn[];
  activeTurn: ClassroomQaActiveTurn | null;
  error: string | null;
};

export type ClassroomQaEvent =
  | { type: 'open' }
  | { type: 'close' }
  | { type: 'cancel_draft' }
  | { type: 'session_loaded'; turns: ClassroomQaTurn[] }
  | { type: 'submit'; question: string; clientTurnId: string }
  | {
      type: 'turn_received';
      clientTurnId: string;
      turn: ClassroomQaTurn;
    }
  | { type: 'answer_playing'; clientTurnId: string }
  | { type: 'answer_finished'; clientTurnId: string }
  | { type: 'fail'; clientTurnId: string; message: string }
  | { type: 'retry' }
  | { type: 'give_up' }
  | { type: 'resume_complete'; keepOpen: boolean }
  | { type: 'reset' };

export const INITIAL_CLASSROOM_QA_STATE: ClassroomQaState = {
  phase: 'closed',
  isOpen: false,
  turns: [],
  activeTurn: null,
  error: null,
};

export function reduceClassroomQa(
  state: ClassroomQaState,
  event: ClassroomQaEvent,
): ClassroomQaState {
  switch (event.type) {
    case 'open':
      if (state.phase !== 'closed') return { ...state, isOpen: true };
      return { ...state, phase: 'drafting', isOpen: true, error: null };
    case 'close':
      if (state.phase === 'drafting') {
        return { ...state, phase: 'closed', isOpen: false, error: null };
      }
      return { ...state, isOpen: false };
    case 'cancel_draft':
      if (state.phase !== 'drafting') return state;
      return { ...state, phase: 'closed', isOpen: false, error: null };
    case 'session_loaded':
      return { ...state, turns: [...event.turns] };
    case 'submit': {
      if (state.activeTurn) throw new Error('classroom QA turn already active');
      if (state.phase !== 'drafting') {
        throw new Error(`cannot submit from ${state.phase}`);
      }
      const question = event.question.trim();
      if (!question) throw new Error('question must not be blank');
      return {
        ...state,
        phase: 'submitting',
        isOpen: true,
        error: null,
        activeTurn: {
          clientTurnId: event.clientTurnId,
          question,
          turn: null,
        },
      };
    }
    case 'turn_received': {
      if (!ownsActiveTurn(state, event.clientTurnId)) return state;
      const turns = state.turns.some(
        (candidate) => candidate.client_turn_id === event.turn.client_turn_id,
      )
        ? state.turns
        : [...state.turns, event.turn];
      return {
        ...state,
        phase:
          event.turn.tts_status === 'ready' && event.turn.audio_url
            ? 'loading_audio'
            : 'playing_answer',
        turns,
        activeTurn: { ...state.activeTurn!, turn: event.turn },
      };
    }
    case 'answer_playing':
      if (!ownsActiveTurn(state, event.clientTurnId)) return state;
      return { ...state, phase: 'playing_answer' };
    case 'answer_finished':
      if (!ownsActiveTurn(state, event.clientTurnId)) return state;
      return { ...state, phase: 'resuming' };
    case 'fail':
      if (!ownsActiveTurn(state, event.clientTurnId)) return state;
      return { ...state, phase: 'error', error: event.message };
    case 'retry':
      if (state.phase !== 'error' || !state.activeTurn) return state;
      return { ...state, phase: 'submitting', error: null };
    case 'give_up':
      if (state.phase !== 'error' || !state.activeTurn) return state;
      return { ...state, phase: 'resuming', error: null };
    case 'resume_complete':
      return {
        ...state,
        phase: event.keepOpen ? 'drafting' : 'closed',
        isOpen: event.keepOpen,
        activeTurn: null,
        error: null,
      };
    case 'reset':
      return { ...INITIAL_CLASSROOM_QA_STATE };
  }
}

function ownsActiveTurn(state: ClassroomQaState, clientTurnId: string): boolean {
  return state.activeTurn?.clientTurnId === clientTurnId;
}
