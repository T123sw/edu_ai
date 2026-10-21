import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ClassroomReadingContext, PlaybackStatus } from '../classroom/reading';
import type { NativePlaybackCheckpoint } from '../classroom/playbackTypes';
import { API_BASE_URL, apiRequest } from '../stitch/api/client';
import type { ClassroomMaterial } from '../stitch/api/types';
import { useAuthSession } from '../stitch/authSession';
import { useClassroomInterruption, type InterruptionPlayback } from '../stitch/classroomQa/useClassroomInterruption';
import type { ClassroomPlaybackSurfaceProps } from '../stitch/course/classroomCatalog/ClassroomPlaybackSurface';
import { positionAt, WatchedIntervals } from './timeline';
import type { HyperframesContent, PlaybackSession } from './types';
import { ResourceLearningTracker } from '../classroom/resourceLearningTracker';
import { startResourceLearningSession, sendResourceLearningEvents, endResourceLearningSession } from '../stitch/api/resourceLearning';
import { useCourseRoute } from '../stitch/course/CourseRouteProvider';
import { shouldTrackResourceLearning } from '../stitch/pages/classroomResourceLearning';
import './classroom.css';

type Props = ClassroomPlaybackSurfaceProps & { content: HyperframesContent; material: ClassroomMaterial };
function projectUrl(path: string): string {
  if (!path.startsWith('/api/hyperframes/projects/')) throw new Error('课堂文件地址无效');
  return new URL(`${API_BASE_URL}${path}`, location.href).href;
}
function playVideo(video: HTMLVideoElement, onFailure: (message: string) => void) {
  void video.play().catch((error: unknown) => {
    // Seeking, switching lessons or pausing can cancel a pending play normally.
    if (error instanceof DOMException && error.name === 'AbortError') return;
    onFailure('浏览器暂未开始播放，请点击播放继续。');
  });
}
export function HyperframesClassroom(props: Props) {
  const { content, material, courseId, classroomId, externallyPaused = false, qaTargetKey, kind, onQaControllerChange } = props;
  const version = material.version ?? props.resourceVersion;
  const { user } = useAuthSession();
  const storageKey = `hyperframes-position:${user?.username}:${courseId}:${classroomId}:${version}:${content.project.digest}`;
  const start = useRef<number>();
  if (start.current === undefined) {
    let saved: number | undefined; try { const value = sessionStorage.getItem(storageKey); if (value !== null && Number.isFinite(Number(value))) saved = Number(value); } catch { /* storage is optional */ }
    const segment = content.timeline.segments.find(s => s.id === props.initialSegmentId);
    start.current = positionAt(content, props.restoreSavedPosition && saved !== undefined ? saved : props.initialSeconds ?? segment?.start ?? saved ?? 0).seconds;
  }
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<HTMLVideoElement>();
  const position = useRef(start.current);
  const statusRef = useRef<PlaybackStatus>('idle');
  const [status, setStatus] = useState<PlaybackStatus>('idle');
  const [session, setSession] = useState<PlaybackSession>();
  const [error, setError] = useState('');
  const [audioError, setAudioError] = useState('');
  const [retry, setRetry] = useState(0);
  const [rate, setRate] = useState(1);
  const [volume, setVolume] = useState(1);
  const callbacks = useRef(props); callbacks.current = props;
  const watched = useRef(new WatchedIntervals());
  const tracker = useRef<ResourceLearningTracker>();
  const { courseRole } = useCourseRoute();
  const tracksLearning = !props.exactMaterial && shouldTrackResourceLearning({ role: user?.role, courseRole, resourceVersion: version ?? null });
  useEffect(() => {
    if (!tracksLearning || !version) return;
    let active = true; let local: ResourceLearningTracker | undefined; let timer: ReturnType<typeof setInterval> | undefined; let id: string | undefined;
    void startResourceLearningSession(courseId, classroomId, version).then(session => {
      id = session.session_id;
      if (!active) { void endResourceLearningSession(courseId, classroomId, version, id).catch(() => undefined); return; }
      local = new ResourceLearningTracker({ outboxKey: `${courseId}:${classroomId}:${version}:${id}`, send: events => sendResourceLearningEvents(courseId, classroomId, version, session.session_id, events) });
      tracker.current = local;
      timer = setInterval(() => { void local?.flush().catch(() => undefined); }, 10000);
    }).catch(() => { if (active) setAudioError('学习记录暂未连接，播放仍可继续。'); });
    return () => { active = false; clearInterval(timer); if (tracker.current === local) tracker.current = undefined; if (local && id) void local.dispose().finally(() => endResourceLearningSession(courseId, classroomId, version, id!)).catch(() => undefined); };
  }, [tracksLearning, courseId, classroomId, version]);
  const publish = useCallback((time: number, state = statusRef.current, ended = false) => {
    const locator = positionAt(content, time); position.current = locator.seconds;
    statusRef.current = state; setStatus(state);
    try { sessionStorage.setItem(storageKey, String(locator.seconds)); } catch { /* storage is optional */ }
    callbacks.current.onPositionChange?.(locator.seconds);
    const context: ClassroomReadingContext = { status: state, position: { seconds: locator.seconds, segment_id: locator.segment_id }, content_hash: content.project.digest };
    if (version) callbacks.current.onReadingContext?.(locator.segment_id || '', version, ended, context);
  }, [content, storageKey, version]);
  const interrupted = useRef(false);
  const playback = useMemo<InterruptionPlayback>(() => ({
    snapshot: () => ({ sceneIndex: -1, revision: 0, status: statusRef.current }),
    interrupt: () => {
      if (!player.current || player.current.readyState < 1) return null;
      const checkpoint: NativePlaybackCheckpoint = { ...positionAt(content, player.current.currentTime), sceneIndex: -1, pageRevision: 0, wasPlaying: !player.current.paused };
      interrupted.current = true; player.current.pause(); watched.current.reset(); publish(checkpoint.seconds, 'interrupted');
      return checkpoint;
    },
    resumeInterrupted: checkpoint => {
      if (!('kind' in checkpoint) || (!player.current || player.current.readyState < 1) || checkpoint.content_hash !== content.project.digest) return false;
      interrupted.current = false; watched.current.reset(); player.current.currentTime = checkpoint.seconds; publish(checkpoint.seconds, 'paused');
      if (checkpoint.wasPlaying && !callbacks.current.externallyPaused) playVideo(player.current, setAudioError);
      return true;
    },
  }), [content, publish]);
  const qa = useClassroomInterruption({ courseId, classroomId, resourceVersion: version, playback, pageRevision: 0, enabled: !!version });
  useEffect(() => {
    const key = qaTargetKey ?? `${kind ?? 'classroom'}:${classroomId}:v${version ?? 'none'}`;
    onQaControllerChange?.(key, { key, controller: qa, canAsk: !!session && !error && status !== 'interrupted', title: content.title || material.title || 'AI 课堂', kind: kind ?? 'classroom', kindLabel: 'AI 课堂', scopeLabel: '已读取课堂时间轴', resourceId: classroomId, resourceVersion: version ?? null, version: version ?? null });
    return () => onQaControllerChange?.(key, null);
  }, [qaTargetKey, kind, onQaControllerChange, classroomId, version, qa, session, error, status, content.title, material.title]);
  useEffect(() => {
    const abort = new AbortController(); setError(''); setSession(undefined);
    if (!version) { setError('课堂缺少精确版本，无法播放'); return; }
    void apiRequest<PlaybackSession>(`/api/self-learning/courses/${encodeURIComponent(courseId)}/materials/classroom/${encodeURIComponent(classroomId)}/versions/${version}/playback`, { method: 'POST', signal: abort.signal }).then(result => {
      if (abort.signal.aborted) return;
      if (result.project_digest !== content.project.digest) throw new Error('课堂文件版本不一致，请重新打开');
      projectUrl(result.project_url); setSession(result);
    }).catch(e => { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : '课堂会话读取失败'); });
    return () => abort.abort();
  }, [courseId, classroomId, version, content.project.digest, retry]);
  useEffect(() => {
    if (!session || !host.current) return;
    const element = document.createElement('video');
    let active = true;
    const restorePosition = position.current;
    const observations = watched.current;
    // Play the exact exported mix. Native HTML remains available in the project
    // download; teaching context continues to use the same immutable timeline.
    const src = new URL(projectUrl(session.exports.video));
    src.searchParams.delete('download');
    element.controls = true;
    element.playsInline = true;
    element.preload = 'auto';
    element.src = src.href;
    element.setAttribute('aria-label', '课堂视频播放器');
    const emit = (state?: PlaybackStatus, ended = false) => { if (active) publish(element.currentTime, interrupted.current ? 'interrupted' : state ?? (element.paused ? statusRef.current === 'completed' ? 'completed' : 'paused' : 'playing'), ended); };
    element.addEventListener('loadedmetadata', () => { if (!active) return; element.currentTime = restorePosition; element.playbackRate = rate; element.volume = volume; publish(restorePosition, 'paused'); });
    element.addEventListener('timeupdate', () => { if (!active) return; const range = observations.sample(element.currentTime, !element.paused && !document.hidden, element.playbackRate);
      if (range) for (const segment of content.timeline.segments) {
        const from = Math.max(range[0], segment.start), to = Math.min(range[1], segment.end);
        if (to > from) tracker.current?.recordRange(segment.id, (from - segment.start) * 1000, (to - segment.start) * 1000);
      }
      emit(); });
    element.addEventListener('seeking', () => observations.reset());
    element.addEventListener('seeked', () => emit());
    element.addEventListener('ratechange', () => { if (active) { setRate(element.playbackRate); observations.reset(); } });
    element.addEventListener('volumechange', () => { if (active) setVolume(element.muted ? 0 : element.volume); });
    element.addEventListener('play', () => { if (interrupted.current || callbacks.current.externallyPaused) { element.pause(); return; } setAudioError(''); observations.reset(); emit('playing'); });
    element.addEventListener('pause', () => { observations.reset(); emit('paused'); });
    element.addEventListener('ended', () => { observations.reset(); emit('completed', true); });
    element.addEventListener('error', () => { if (!active) return; element.pause(); setError('视频未能加载，或播放授权已过期。请重试，当前位置会保留。'); });
    player.current = element; host.current.appendChild(element);
    const expiry = window.setTimeout(() => { if (!active) return; element.pause(); setError('播放授权已过期，请刷新授权后继续。当前位置已保留。'); }, Math.max(0, session.expires_at * 1000 - Date.now()));
    return () => { active = false; clearTimeout(expiry); element.pause(); element.removeAttribute('src'); element.load(); element.remove(); if (player.current === element) player.current = undefined; observations.reset(); };
    // User controls update properties without reloading the project.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, publish]);
  useEffect(() => { if (host.current) host.current.inert = status === 'interrupted' || externallyPaused || !!error; }, [status, externallyPaused, error]);
  const resumeExternal = useRef(false);
  useEffect(() => {
    if (externallyPaused) { resumeExternal.current = !!player.current && !player.current.paused; player.current?.pause(); }
    else if (resumeExternal.current) { resumeExternal.current = false; if (!interrupted.current && player.current) playVideo(player.current, setAudioError); }
  }, [externallyPaused]);
  useEffect(() => {
    const command = props.playbackCommand;
    if (!command) return;
    // Asking the learning agent pauses once, without making controls inert.
    // A question asked while the mobile panel is hidden also cancels auto-resume.
    if (command.action === 'pause') {
      resumeExternal.current = false;
      player.current?.pause();
    } else if (!interrupted.current && !callbacks.current.externallyPaused && player.current) {
      playVideo(player.current, setAudioError);
    }
  }, [props.playbackCommand]);
  return <section className="hf-classroom" aria-label="HyperFrames 课堂">
    <header className="hf-heading">
      <h2>{content.title || material.title || 'AI 课堂'}</h2>
      {session && !error && <details className="hf-export">
        <summary aria-label="导出课堂资源"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M5 16v4h14v-4" /></svg>导出</summary>
        <nav aria-label="课堂下载">
          <a href={projectUrl(session.exports.video)} download>视频 MP4</a>
          <a href={projectUrl(session.exports.subtitles)} download>字幕 SRT</a>
          <a href={projectUrl(session.exports.project)} download>HTML 项目 ZIP</a>
        </nav>
      </details>}
    </header>
    {error && <p role="alert">{error} <button onClick={() => setRetry(n => n + 1)}>刷新播放授权</button></p>}
    {!session && !error && <p role="status">正在准备视频与讲解…</p>}
    {audioError && <p role="alert">{audioError}</p>}
    <div ref={host} className="hf-player" />
  </section>;
}
