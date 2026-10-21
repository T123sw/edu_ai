import type { PlaybackStatus } from './reading';
import type { HyperframesLocator } from '../hyperframes/types';
// A user action is consumed once; it must not lock the native player controls.
export type PlaybackCommand = { action: 'pause' | 'resume'; sequence: number };
export type PagePlaybackSnapshot = { sceneIndex: number; status: PlaybackStatus; revision: number };
export type PagePlaybackCheckpoint = { sceneId: string; actionIndex: number; actionId: string | null; phase: 'executing_action' | 'between_actions'; sceneIndex: number; pageRevision: number };
export type NativePlaybackCheckpoint = HyperframesLocator & { pageRevision: number; sceneIndex: number; wasPlaying: boolean };
export type InterruptionCheckpoint = PagePlaybackCheckpoint | NativePlaybackCheckpoint;
