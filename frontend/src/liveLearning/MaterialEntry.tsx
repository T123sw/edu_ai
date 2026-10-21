import { ReportReading } from './ReportReading';
import { courseMaterialToMarkdown } from '../stitch/api/courses';
import type { ClassroomReadingContext } from '../classroom/reading';
import type { PlaybackCommand } from '../classroom/playbackTypes';
import { refKey, type ResourceRef, type Locator, type PracticeContext } from './readingContext';
import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AuthSessionProvider } from '../stitch/authSession';
import { CourseRouteProvider } from '../stitch/course/CourseRouteProvider';
const ClassroomPlaybackSurface = lazy(() => import('../stitch/course/classroomCatalog/ClassroomPlaybackSurface').then(m => ({ default: m.ClassroomPlaybackSurface })));
const CourseMaterialArtifactPreview = lazy(() => import('../stitch/pages/CourseMaterialArtifactPreview').then(m => ({ default: m.CourseMaterialArtifactPreview })));
import { apiRequest } from '../stitch/api/client';
import type { ClassroomMaterial, CourseMaterial } from '../stitch/api/types';
import '../stitch/styles.css';
import './live.css';
import '../selfLearning/classroomEditorial.css';
import { LiveQuiz, QuizLoading } from './Quiz';
function Material() {
  const { user, authReady } = useAuth();
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const courseId = params.get('course_id') || '', materialId = params.get('material_id') || '', kind = params.get('material_type') || '';
  const version = Number(params.get('version'));
  const binding = useRef<{ channel_id: string; resource_ref: ResourceRef; sequence: number }>();
  const loaded = useRef(false);
  const selectedText = useRef('');
  const practiceContext = useRef<PracticeContext>();
  const documentLocator = useRef<Locator>();
  const [clearSelection, setClearSelection] = useState(0);
  const [canReference, setCanReference] = useState(false);
  const lastScene = useRef<{ scene_id: string; reached_end: boolean; classroom: ClassroomReadingContext }>();
  const [material, setMaterial] = useState<CourseMaterial>();
  const [classroom, setClassroom] = useState<ClassroomMaterial>();
  const [error, setError] = useState('');
  const [paused, setPaused] = useState(false);
  const [playbackCommand, setPlaybackCommand] = useState<PlaybackCommand>();
  const initialPosition = Number(params.get('position')) || 0;
  const initialBlockId = params.get('block_id') || undefined;
  const questionParam = params.get('question_index');
  const initialQuestion = questionParam !== null && /^\d+$/.test(questionParam) ? Number(questionParam) : undefined;
  const emit = useCallback((locator: Locator, reached_end = false, classroom?: ClassroomReadingContext, intent?: 'ask', question_prompt?: string) => {
    const context = binding.current;
    if (!context || !loaded.current) return;
    parent.postMessage({ type: 'learning-reading-context', channel_id: context.channel_id, resource_ref: context.resource_ref, sequence: ++context.sequence, locator, reached_end, selected_text: selectedText.current, classroom: classroom && { status: classroom.status, position: classroom.position, lecture: classroom.lecture }, practice: locator.kind === 'quiz' ? practiceContext.current : undefined, intent, question_prompt }, location.origin);
  }, []);
  const onClassroomReading = useCallback((scene_id: string, actualVersion: number, reached_end: boolean, classroom: ClassroomReadingContext) => {
    if (actualVersion !== version) return;
    loaded.current = true;
    lastScene.current = { scene_id, reached_end, classroom };
    if (!binding.current) parent.postMessage({ type: 'learning-context-request' }, location.origin);
    else emit(classroom.position ? { kind: 'hyperframes', ...classroom.position, content_hash: classroom.content_hash } : { kind: 'classroom', scene_id }, reached_end, classroom);
  }, [version, emit]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      const data = event.data;
      const ref = { course_id: courseId, material_type: kind, material_id: materialId, version };
      if (event.source === parent && event.origin === location.origin && data?.type === 'learning-clear-selection' && data.channel_id === binding.current?.channel_id) { selectedText.current = ''; practiceContext.current = undefined; documentLocator.current = undefined; emit({ kind: 'document', scroll_top: scrollY }); setClearSelection(n => n + 1); return; }
      if (event.source !== parent || event.origin !== location.origin || data?.type !== 'learning-context-init' || !data.resource_ref || refKey(data.resource_ref) !== refKey(ref) || !loaded.current) return;
      if (typeof data.channel_id !== 'string' || !data.channel_id) return;
      binding.current = { channel_id: data.channel_id, resource_ref: ref, sequence: 0 };
      setCanReference(data.can_reference === true);
      parent.postMessage({ type: 'learning-context-ready', channel_id: data.channel_id, resource_ref: ref }, location.origin);
      if (lastScene.current) emit(lastScene.current.classroom.position ? { kind: 'hyperframes', ...lastScene.current.classroom.position, content_hash: lastScene.current.classroom.content_hash } : { kind: 'classroom', scene_id: lastScene.current.scene_id }, lastScene.current.reached_end, lastScene.current.classroom);
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [courseId, kind, materialId, version, emit]);
  const positionChange = useCallback((position: number) => { parent.postMessage({ type: 'learning-position', position }, location.origin); }, []);
  useEffect(() => {
    const receive = (e: MessageEvent) => {
      if (e.source !== parent || e.origin !== location.origin) return;
      if (e.data?.type === 'learning-pause') setPaused(!!e.data.paused);
      const command = e.data?.command;
      if (e.data?.type === 'learning-playback-command' && (command?.action === 'pause' || command?.action === 'resume') && Number.isSafeInteger(command.sequence) && command.sequence > 0) {
        setPlaybackCommand(previous => previous && previous.sequence >= command.sequence ? previous : command);
      }
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, []);
  useLayoutEffect(() => { if (material && !initialBlockId && initialQuestion === undefined) scrollTo(0, initialPosition); }, [material, initialPosition, initialBlockId, initialQuestion]);
  useEffect(() => {
    if (!material || kind === 'classroom') return;
    let pending: ReturnType<typeof setTimeout> | undefined;
    const scroll = () => {
      positionChange(scrollY);
      if (!pending) pending = setTimeout(() => { pending = undefined; emit(documentLocator.current?.kind === 'quiz' ? documentLocator.current : { ...documentLocator.current, kind: 'document', scroll_top: scrollY }, scrollY + innerHeight >= document.documentElement.scrollHeight - 4); }, 750);
    };
    const selection = () => {
      if (kind === 'report' || kind === 'quiz') return;
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
  if (!authReady) return kind === 'quiz' ? <main className="sl-editorial-material"><QuizLoading /></main> : <p>正在读取资料…</p>;
  if (!user) return <p role="alert">登录已过期，请返回首页登录。</p>;
  if (error) return <p role="alert">{error}</p>;
  return <AuthSessionProvider user={{ ...user, role: user.role === 'teacher' || user.role === 'admin' ? user.role : 'student' }} authenticated><CourseRouteProvider enabled={kind !== 'quiz'}><Suspense fallback={kind === 'quiz' ? <main className="sl-editorial-material"><QuizLoading /></main> : <p>正在读取资料…</p>}><main className={`sl-editorial-material ${kind === 'classroom' ? 'sl-material-playback' : ''}`}>
    {kind === 'classroom' ? classroom ? <ClassroomPlaybackSurface exactMaterial={classroom} initialSceneId={params.get('scene_id') || undefined} resourceVersion={version} onReadingContext={onClassroomReading} initialScene={initialPosition} initialSeconds={params.has('seconds') ? Number(params.get('seconds')) : undefined} initialSegmentId={params.get('segment_id') || undefined} restoreSavedPosition={params.get('citation') !== '1'} externallyPaused={paused} playbackCommand={playbackCommand} onPositionChange={positionChange} courseId={courseId} classroomId={materialId} mode="learn" kind={params.get('visibility') === 'private' ? 'personal_classroom' : 'classroom'} /> : <p>正在读取资料…</p> : material ? kind === 'quiz' ? <LiveQuiz material={material} initialQuestion={initialQuestion} onPracticeUpdate={(index, practice) => { if (documentLocator.current?.kind === 'quiz' && documentLocator.current.question_index === index) { practiceContext.current = practice; emit(documentLocator.current); } }} onReference={canReference ? (index, stem, practice, prompt) => { selectedText.current = stem.slice(0, 10000); practiceContext.current = practice; documentLocator.current = { kind: 'quiz', question_index: index }; emit(documentLocator.current, false, undefined, 'ask', prompt); } : undefined} /> : kind === 'report' ? <ReportReading enabled={canReference} initialBlockId={initialBlockId} markdown={courseMaterialToMarkdown(material)} clearSignal={clearSelection} onReference={(text, locator, intent) => { selectedText.current = text; documentLocator.current = locator; emit(locator, false, undefined, intent); }}><CourseMaterialArtifactPreview material={material} readingAnchors /></ReportReading> : <CourseMaterialArtifactPreview material={material} /> : kind === 'quiz' ? <QuizLoading /> : <p>正在读取资料…</p>}
  {params.get('citation') === '1' && !initialBlockId && initialQuestion === undefined && !params.get('scene_id') && !params.has('seconds') && <p role="status">此来源没有精确位置，已打开原版本资料。</p>}
  {material && <div data-reading-end aria-label="资料末尾" />}</main></Suspense></CourseRouteProvider></AuthSessionProvider>;
}
export default function MaterialEntry() { return <AuthProvider><Material /></AuthProvider>; }
