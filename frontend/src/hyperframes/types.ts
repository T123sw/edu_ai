export type HyperframesLocator = { kind: 'hyperframes'; seconds: number; segment_id?: string; content_hash?: string };
export type HyperframesSegment = { id: string; title: string; start: number; end: number; narration: string; visual_description: string; audio_path?: string; events?: { start: number; end: number; description: string; target?: string }[] };
export type HyperframesContent = { format: 'hyperframes/v1'; title?: string; project: { id: string; digest: string; entry: string }; timeline: { duration: number; segments: HyperframesSegment[] } };
export type PlaybackSession = { project_url: string; expires_at: number; project_digest: string; duration: number; exports: { video: string; subtitles: string; project: string } };
export function nativeContent(value: unknown): HyperframesContent | undefined {
  if (!value || typeof value !== 'object') return;
  const body = value as Partial<HyperframesContent> & { content?: unknown };
  if (body.format === 'hyperframes/v1' && body.project?.digest && Number.isFinite(body.timeline?.duration) && Array.isArray(body.timeline?.segments)) return body as HyperframesContent;
  if (body.content) return nativeContent(body.content);
}
