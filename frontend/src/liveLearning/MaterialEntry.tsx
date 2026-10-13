import { refKey, type ResourceRef, type Locator } from './readingContext';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AuthSessionProvider } from '../stitch/authSession';
import { CourseRouteProvider } from '../stitch/course/CourseRouteProvider';
import { ClassroomPlaybackSurface } from '../stitch/course/classroomCatalog/ClassroomPlaybackSurface';
import { CourseMaterialArtifactPreview } from '../stitch/pages/CourseMaterialArtifactPreview';
import { apiRequest } from '../stitch/api/client';
import type { ClassroomMaterial, CourseMaterial } from '../stitch/api/types';
import '../stitch/styles.css';
import './live.css';
import '../selfLearning/classroomEditorial.css';
import { LiveQuiz } from './Quiz';
function Material() {
  const { user, authReady } = useAuth();
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const courseId = params.get('course_id') || '', materialId = params.get('material_id') || '', kind = params.get('material_type') || '';
  const version = Number(params.get('version'));
  const binding = useRef<{ channel_id: string; resource_ref: ResourceRef; sequence: number }>();
  const loaded = useRef(false);
  const selectedText = useRef('');
  const lastScene = useRef<{ scene_id: string; reached_end: boolean }>();
  const [material, setMaterial] = useState<CourseMaterial>();
  const [classroom, setClassroom] = useState<ClassroomMaterial>();
  const [error, setError] = useState('');
  const [paused, setPaused] = useState(false);
  const initialPosition = Number(params.get('position')) || 0;
  const emit = useCallback((locator: Locator, reached_end = false) => {
    const context = binding.current;
    if (!context || !loaded.current) return;
    parent.postMessage({ type: 'learning-reading-context', channel_id: context.channel_id, resource_ref: context.resource_ref, sequence: ++context.sequence, locator, reached_end, selected_text: selectedText.current }, location.origin);
  }, []);
  const onClassroomReading = useCallback((scene_id: string, actualVersion: number, reached_end: boolean) => {
    if (actualVersion !== version) return;
    loaded.current = true;
    lastScene.current = { scene_id, reached_end };
    if (!binding.current) parent.postMessage({ type: 'learning-context-request' }, location.origin);
    else emit({ kind: 'classroom', scene_id }, reached_end);
  }, [version, emit]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      const data = event.data;
      const ref = { course_id: courseId, material_type: kind, material_id: materialId, version };
      if (event.source !== parent || event.origin !== location.origin || data?.type !== 'learning-context-init' || !data.resource_ref || refKey(data.resource_ref) !== refKey(ref) || !loaded.current) return;
      if (typeof data.channel_id !== 'string' || !data.channel_id) return;
      binding.current = { channel_id: data.channel_id, resource_ref: ref, sequence: 0 };
      parent.postMessage({ type: 'learning-context-ready', channel_id: data.channel_id, resource_ref: ref }, location.origin);
      if (lastScene.current) emit({ kind: 'classroom', scene_id: lastScene.current.scene_id }, lastScene.current.reached_end);
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [courseId, kind, materialId, version, emit]);
  const positionChange = useCallback((position: number) => { parent.postMessage({ type: 'learning-position', position }, location.origin); }, []);
  useEffect(() => {
    const receive = (e: MessageEvent) => { if (e.source === parent && e.origin === location.origin && e.data?.type === 'learning-pause') setPaused(!!e.data.paused); };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, []);
  useLayoutEffect(() => { if (material) scrollTo(0, initialPosition); }, [material, initialPosition]);
  useEffect(() => {
    if (!material || kind === 'classroom') return;
    let pending: ReturnType<typeof setTimeout> | undefined;
    const scroll = () => {
      positionChange(scrollY);
      if (!pending) pending = setTimeout(() => { pending = undefined; emit({ kind: 'document', scroll_top: scrollY }, scrollY + innerHeight >= document.documentElement.scrollHeight - 4); }, 750);
    };
    const selection = () => {
      const text = (window.getSelection()?.toString() || '').slice(0, 10000);
      if (text || document.hasFocus()) selectedText.current = text;
      emit({ kind: 'document', scroll_top: scrollY });
    };
    document.addEventListener('selectionchange', selection);
    window.addEventListener('scroll', scroll);
    return () => { clearTimeout(pending); document.removeEventListener('selectionchange', selection); window.removeEventListener('scroll', scroll); };
  }, [material, kind, initialPosition, positionChange, emit]);
  useEffect(() => {
    if (!user) return;
    let active = true;
    void apiRequest<CourseMaterial & ClassroomMaterial>(`/api/self-learning/courses/${encodeURIComponent(courseId)}/materials/${encodeURIComponent(kind)}/${encodeURIComponent(materialId)}/versions/${version}`).then(m => { if (!active) return; if (m.version !== version) throw new Error('资料版本已变化，请返回课堂刷新后重新打开'); if (kind === 'classroom') setClassroom(m); else setMaterial(m); loaded.current = true; parent.postMessage({ type: 'learning-context-request' }, location.origin); }).catch(e => active && setError(e.message));
    return () => { active = false; };
  }, [courseId, kind, materialId, version, user]);
  if (!authReady) return <p>正在读取资料…</p>;
  if (!user) return <p role="alert">登录已过期，请返回首页登录。</p>;
  if (error) return <p role="alert">{error}</p>;
  return <AuthSessionProvider user={{ ...user, role: user.role === 'teacher' || user.role === 'admin' ? user.role : 'student' }} authenticated><CourseRouteProvider enabled><main className="sl-editorial-material">
    {kind === 'classroom' ? classroom ? <ClassroomPlaybackSurface exactMaterial={classroom} initialSceneId={params.get('scene_id') || undefined} resourceVersion={version} onReadingContext={onClassroomReading} initialScene={initialPosition} externallyPaused={paused} onPositionChange={positionChange} courseId={courseId} classroomId={materialId} mode="learn" kind={params.get('visibility') === 'private' ? 'personal_classroom' : 'classroom'} /> : <p>正在读取资料…</p> : material ? kind === 'quiz' ? <LiveQuiz material={material} /> : <CourseMaterialArtifactPreview material={material} /> : <p>正在读取资料…</p>}
  {material && <div data-reading-end aria-label="资料末尾" />}</main></CourseRouteProvider></AuthSessionProvider>;
}
export default function MaterialEntry() { return <AuthProvider><Material /></AuthProvider>; }
