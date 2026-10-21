export type PlaybackStatus = 'idle' | 'playing' | 'paused' | 'interrupted' | 'completed';
/** Historical positions are retained only to read archived learning records. */
export type LecturePosition = { scene_id: string; action_id: string; speech_action_id?: string; sentence_index?: number; sentence_alignment?: 'estimated' | 'sentence'; speech_completed: boolean; highlighted_element_ids: string[] };
export type ClassroomReadingContext = { status: PlaybackStatus; position?: { seconds: number; segment_id?: string }; content_hash?: string; lecture?: LecturePosition };
