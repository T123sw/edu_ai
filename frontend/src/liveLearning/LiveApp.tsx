import { ExamWorkspace } from '../exam/ExamWorkspace';
import {RecentOpenProvider} from '../recent/RecentOpenProvider';
import {useRecentOpens} from '../recent/context';
import {recentKey} from '../recent/store';
import { ThemeSwitcher } from "../stitch/theme/ThemeSwitcher";
import { PblWorkspace } from '../pbl/PblWorkspace';
import { Practice } from '../practice/Practice';
import { BubbleSortPrototype } from '../practice/teaching/BubbleSortPrototype';
import { PracticeHome, ExamHome } from '../practice/PracticeHome';
import { usePracticeHome } from '../practice/usePracticeHome';
import { serialPolling } from './serialPolling';
import { refreshLearningState, type LiveLearningState as State } from './stateRefresh';
import { mergeProgressiveCourse, withResourcePlaceholders } from './progressiveCourse';
import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiRequest } from '../stitch/api/client';
import { courseMaterialToMarkdown } from '../stitch/api/courses';
import type { CourseMaterial } from '../stitch/api/types';
import { Studio } from '../studio/StudioHome';
import { Home } from '../selfLearning/Home';
import { Classroom } from '../selfLearning/Classroom';
import { ResourceCenter } from '../selfLearning/Library';
import { Brand, Empty } from '../selfLearning/ui';
import { uid, type Classroom as Room, type LearningState, type LearningResource } from '../selfLearning/model';
import '../selfLearning/styles.css';
import '../selfLearning/review.css';
import './live.css';
import '../selfLearning/homeRefresh.css';
import { TaskCenter, TaskLauncher } from './TaskCenter';

import { ModuleNavigation } from './ModuleNavigation';
import './moduleNavigation.css';
import { PreparationOptionsForm, defaultOptions } from './Preparation';
import { usePreparationProgress } from './usePreparationProgress';
import { PreparationProgress } from './PreparationProgress';
import { preparationJob } from './preparationProgress';

const base = '/api/self-learning';
const pathFor = (id: string) => `${base}/courses/${encodeURIComponent(id)}`;
const empty: State = { version: 1, rooms: [], resources: [], jobs: [], shared: [], serverJobs: [] };
export default function LiveApp() {
  const {user}=useAuth();
  return <RecentOpenProvider owner={`user:${user?.username||''}`}><LiveLearning /></RecentOpenProvider>;
}
function LiveLearning() {
  const recent=useRecentOpens();
  const { user } = useAuth();
  const preparation = usePreparationProgress(user?.username || '');
  const [data, update] = useState<State>(empty);
  const current = useRef(data);
  const visibleJobs = [...preparation.tasks.map(preparationJob), ...data.serverJobs];
  const [hash, setHash] = useState(location.hash);
  const [classroomPrompt, setClassroomPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [tasks, setTasks] = useState(false);
  const pending = useRef(new Map<string, Record<string, unknown>>());
  const saveTimer = useRef<ReturnType<typeof setTimeout>>();
  const saving = useRef<Promise<void> | null>(null);
  const revision = useRef(0);
  const questions = useRef(new Map<string, string>());
  const [preparationOptions, setPreparationOptions] = useState(defaultOptions);
  const [preparationUploading, setPreparationUploading] = useState(false);
  const [path, raw = ''] = hash.replace(/^#/, '').split('?');
  const query = new URLSearchParams(raw);
  const home = !path || path === '/';
  const library = path === '/resources';
  const myResources = path === '/my-resources' || (home && query.has('resources'));
  const practicePage = path === '/practice' || path?.startsWith('/practice/');
  const examPage = path === '/exam';
  const examId = path?.startsWith('/exam/') ? decodeURIComponent(path.slice(6)) : '';
  const practiceLanding = path === '/practice';
  const bubblePrototype = path === '/practice/bubble-sort';
  const codeLanding = path === '/practice/code';
  const codeExercise = path?.startsWith('/practice/code/') ? decodeURIComponent(path.slice('/practice/code/'.length)) : '';
  const moduleHome = home || practiceLanding || codeLanding || examPage || !!examId || myResources;
  const practiceHome = usePracticeHome(practicePage, practiceLanding || codeLanding ? query.get('topic') || '' : '');
  const roomId = path?.startsWith('/classroom/') ? path.slice(11) : query.get('classroom');
  const room = data.rooms.find(r => r.id === roomId);
  const openedKey=room?recentKey('classroom',room.id):codeExercise?recentKey('project',codeExercise):practicePage&&!practiceLanding&&!codeLanding&&!bubblePrototype?recentKey('practice',path.slice(10)):'';
  const markOpened=recent.mark;
  useEffect(()=>{if(openedKey)markOpened(openedKey);},[openedKey,markOpened]);
  const courseResources = room?.chapters.flatMap(c => c.resources) || [];
  const selectedResource = courseResources.find(r => r.id === query.get('resource')) || courseResources.find(r => r.id === room?.selectedId) || courseResources[0];
  const selectedChapter = room?.chapters.find(c => c.resources.some(r => r.id === selectedResource?.id));
  const commit = useCallback((value: State) => { const normalized = { ...value, rooms: value.rooms.map(withResourcePlaceholders) }; current.current = normalized; update(normalized); }, []);
  const refresh = useCallback(async () => {
    const started = revision.current;
    const activeId = location.hash.split('?')[0].replace('#/classroom/', '');
    const value = await refreshLearningState(current.current, activeId);
    if (started === revision.current && !pending.current.size && !saving.current) {
      const activeId = location.hash.split('?')[0].replace('#/classroom/', '');
      value.rooms = value.rooms.map(next => { const previous = current.current.rooms.find(r => r.id === next.id);
        return next.id === activeId && previous ? mergeProgressiveCourse(previous, next) : next; });
      commit(value);
    } else {
      // Playback and note edits may keep a save pending. They must not starve
      // delivery updates; only merge this preparation's metadata in that case.
      const activeId = location.hash.split('?')[0].replace('#/classroom/', '');
      const previous = current.current.rooms.find(r => r.id === activeId);
      const next = value.rooms.find(r => r.id === activeId);
      if (previous?.preparationDelivery?.state === 'partial' && next &&
          previous.preparationDelivery.preparationId === next.preparationDelivery?.preparationId &&
          previous.manifestRef?.manifest_id === next.manifestRef?.manifest_id) {
        const merged = mergeProgressiveCourse(previous, next);
        if (merged !== previous) commit({ ...current.current, rooms: current.current.rooms.map(r => r.id === activeId
          ? { ...merged, progress: previous.progress, understanding: previous.understanding,
            messages: previous.messages, updatedAt: previous.updatedAt } : r) });
      }
    }
  }, [commit]);
  const flush = useCallback(async () => {
    clearTimeout(saveTimer.current);
    if (saving.current) await saving.current;
    const entries = [...pending.current.entries()];
    if (!entries.length) return;
    pending.current.clear();
    const task = (async () => {
      for (const [index, [id, patch]] of entries.entries()) {
        try { await apiRequest(`${pathFor(id)}/learning`, { method: 'PATCH', body: JSON.stringify(patch), keepalive: true }); }
        catch (cause) { for (const [key, remaining] of entries.slice(index)) pending.current.set(key, { ...remaining, ...pending.current.get(key) }); throw cause; }
      }
    })();
    saving.current = task;
    try { await task; } finally { saving.current = null; }
  }, []);
  const mutate = useCallback((action: SetStateAction<LearningState>) => {
    revision.current++;
    const previous = current.current;
    const next = typeof action === 'function' ? action(previous) : action;
    if (next === previous) return;
    for (const after of next.rooms) {
      const before = previous.rooms.find(r => r.id === after.id);
      if (!before || before === after) continue;
      const patch: Record<string, unknown> = { ...pending.current.get(after.id) };
      if (before.selectedId !== after.selectedId && after.chapters.some(c => c.resources.some(r => r.id === after.selectedId && r.ready))) patch.selectedId = after.selectedId;
      if (!after.progressPersistence && before.progress !== after.progress) patch.progress = { ...(patch.progress as object || {}), ...Object.fromEntries(Object.entries(after.progress).filter(([id, evidence]) => before.progress[id] !== evidence)) };
      if (after.progressPersistence && before.progress !== after.progress) {
        patch.progress = { ...(patch.progress as object || {}), ...Object.fromEntries(Object.entries(after.progress).filter(([id, e]) => before.progress[id]?.note !== e.note).map(([id, e]) => [id, { note: e.note }])) };
      }
      if (!after.progressPersistence && before.understanding !== after.understanding) {
        patch.understanding = Object.fromEntries(after.chapters.map(c => [c.id, after.understanding?.[c.id] || null]));
      }
      if (Object.keys(patch).length) pending.current.set(after.id, patch);
    }
    commit({ ...previous, ...next });
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => { void flush().catch(c => setError(`学习记录尚未保存：${c.message}`)); }, 350);
  }, [commit, flush]);
  useEffect(() => {
    let active = true;
    const stop = serialPolling(async () => {
      await refresh().catch(c => active && setError(c.message)).finally(() => active && setLoading(false));
    }, 5000);
    const route = () => setHash(location.hash);
    const leave = () => { void flush().catch(() => undefined); };
    window.addEventListener('pagehide', leave);
    window.addEventListener('hashchange', route);
    return () => { active = false; stop(); window.removeEventListener('pagehide', leave); window.removeEventListener('hashchange', route); void flush().catch(() => undefined); };
  }, [refresh, flush]);
  const action = async (fn: () => Promise<unknown>, label = '') => {
    setError(''); setBusy(label);
    try { await flush(); await fn(); await refresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : '操作失败，请重试'); }
    finally { setBusy(''); }
  };
  const resourceAction = async (fn: () => Promise<unknown>) => { await flush(); await fn(); await refresh(); };
  const open = async (target: Room) => action(async () => {
    await apiRequest(`${pathFor(target.id)}/learning`, { method: 'PATCH', body: '{}' });
    await refresh(); location.hash = `/classroom/${target.id}`;
  });
  const workbench = (resource?: LearningResource) => {
    const selectedRoom = data.rooms.find(r => r.id === resource?.courseId) || room || data.rooms[0];
    if (!selectedRoom) return '#/';
    const chapter = selectedRoom.chapters.find(c => c.id === resource?.chapterId || c.resources.some(r => r.id === selectedRoom.selectedId));
    const params = new URLSearchParams({ course_id: selectedRoom.id });
    if (chapter) { params.set('scopeType', 'knowledge_point'); params.set('scopeId', chapter.id); params.set('scopeLabel', chapter.title); }
    if (resource?.remote) { params.set('reference', resource.remote.materialId); params.set('material_type', resource.remote.materialType); }
    return `?liveWorkbench=1#${user?.role === 'student' ? 'student-ai' : 'ai'}?${params}`;
  };
  useEffect(() => { if (path === '/studio' && !loading && data.rooms.length) location.replace(workbench()); });
  const materialPath = (resource: LearningResource) => `/api/courses/${encodeURIComponent(resource.remote!.courseId)}/materials/${resource.remote!.materialType}/${encodeURIComponent(resource.remote!.materialId)}`;
  const byId = (id: string) => data.resources.find(r => r.id === id)!;
  return <div className={`sl-app sl-live frontend-review ${!moduleHome ? 'in-course-workspace' : ''} ${room && !library ? 'in-classroom' : ''}`} onClickCapture={e => {
    const link = (e.target as Element).closest('a');
    if (link && /^\?(liveWorkbench|account)=/.test(link.getAttribute('href') || '')) { e.preventDefault(); void action(async () => { location.assign(link.href); }); }
  }}>
    <header className="sl-header sl-module-header">
      <a href="#/" aria-label="返回首页"><Brand /></a>
      <ModuleNavigation active={myResources ? 'resources' : practicePage ? 'practice' : (examPage || examId) ? 'exam' : 'classroom'} classroomHref="#/" />
      <div className="sl-live-account"><TaskLauncher jobs={visibleJobs} open={tasks} onClick={() => setTasks(true)} /><ThemeSwitcher /><a className="sl-avatar" aria-label="个人中心" title={user?.username} href="?account=1#profile">{user?.username.slice(0, 1)}</a></div>
    </header>
    {error && <div className="sl-live-error" role="alert">{error}<button onClick={() => void action(async () => { await flush(); await refresh(); })}>刷新状态</button><button aria-label="关闭提示" onClick={() => setError('')}>×</button></div>}
    {busy && <div className="sl-live-busy" role="status">{busy}</div>}
    {loading ? <p className="sl-auth-loading" role="status">正在读取学习空间…</p> : examId ? <ExamWorkspace key={`${user?.username}:${examId}`} id={examId} owner={user?.username || ''} /> : examPage ? <ExamHome key={user?.username} /> : codeExercise ? <PblWorkspace key={`${user?.username}:${codeExercise}`} exerciseId={codeExercise} owner={user?.username || ''} pendingContent={<PracticeHome state={practiceHome} initialMode="code" />} /> : (practiceLanding || codeLanding) ? <PracticeHome key={user?.username} state={practiceHome} initialMode={codeLanding ? 'code' : 'simulation'} /> : bubblePrototype ? <BubbleSortPrototype key={user?.username} owner={user?.username || ""} embedded /> : practicePage ? <Practice key={path} id={path.slice(10) || undefined} initialTopic="" pendingContent={<PracticeHome state={practiceHome} />} /> : myResources ? <Studio key={`${user?.username}:resources`} view="resources" owner={user?.username || ''} rooms={data.rooms} legacyResources={data.resources} /> : home ? <Home key={user?.username} promptValue={classroomPrompt} onPromptChange={setClassroomPrompt} live canCreateFromUploads={preparationOptions.uploads.length > 0 || preparationUploading} preparationOptions={<PreparationOptionsForm value={preparationOptions} onChange={setPreparationOptions} onUploadingChange={setPreparationUploading} />} rooms={data.rooms} onOpen={r => void open(r)} onCreate={text => {
      if (busy) return;
      if (preparationUploading) { setError('资料仍在上传，请完成后再开始学习'); return; }
      void preparation.submit(text, preparationOptions);
    }} /> : library ? <ResourceCenter room={room} classroomId={room?.id} resources={data.resources} resourceId={query.get('resource') || undefined} workbenchHref={workbench()} workbenchForResource={id => workbench(byId(id))}
      onRename={(id, title) => resourceAction(() => apiRequest(materialPath(byId(id)), { method: 'PATCH', body: JSON.stringify({ title }) }))}
      onRemove={id => resourceAction(() => apiRequest(materialPath(byId(id)), { method: 'DELETE' }))}
      onPin={id => void action(() => apiRequest(materialPath(byId(id)) + '/pin', { method: 'POST', body: JSON.stringify({ is_pinned: !byId(id).pinned }) }))}
      onAddToLearning={(r, chapterId) => { if (room && r.remote) return resourceAction(() => apiRequest(`${pathFor(room.id)}/attachments`, { method: 'POST', body: JSON.stringify({ chapter_id: chapterId, material_id: r.remote!.materialId, material_type: r.remote!.materialType }) })); }}
      onDownload={r => void action(async () => { const material = await apiRequest<CourseMaterial>(materialPath(r)); const content = courseMaterialToMarkdown(material); const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown' })); const a = document.createElement('a'); a.href = url; a.download = r.title.replace(/[\\/:*?"<>|]/g, '-') + '.md'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); })} /> : room ? <Classroom key={`${user?.username}:${room.id}`} room={room} setState={mutate} resourceId={query.get('resource') || undefined} workbenchHref={workbench()} onSelect={id => { location.hash = `/classroom/${room.id}?resource=${encodeURIComponent(id)}`; }} onAsk={async (chapterId, resourceId, text) => {
      await flush();
      const key = JSON.stringify([room.id, chapterId, resourceId, text]);
      const requestId = questions.current.get(key) || uid(); questions.current.set(key, requestId);
      const value = await apiRequest<Room>(`${pathFor(room.id)}/topics/${encodeURIComponent(chapterId)}/turns`, { method: 'POST', body: JSON.stringify({ question: text, resource_id: resourceId, request_id: requestId }) });
      questions.current.delete(key); revision.current++;
      commit({ ...current.current, rooms: current.current.rooms.map(r => r.id === value.id ? { ...value, selectedId: r.selectedId, ...(pending.current.has(r.id) ? { progress: r.progress, understanding: r.understanding } : {}) } : r) });
    }} onRetryNode={room.preparationDelivery ? async nodeId => {
      await apiRequest(`/api/course-preparations/${encodeURIComponent(room.preparationDelivery!.preparationId)}/retry`, {
        method: 'POST', body: JSON.stringify({ node_id: nodeId }),
      });
      await refresh();
    } : undefined} /> : <Empty title="课堂未找到" text="课堂不存在或当前账号无权访问。" action={<a href="#/">返回首页</a>} />}
    {!loading && room && selectedChapter && !library && !moduleHome && <Studio key={`${user?.username}:${room.id}:${selectedChapter.id}`} view="course" owner={user?.username || ''} rooms={data.rooms} room={room} chapter={selectedChapter} legacyResources={data.resources} />}
    {tasks && <TaskCenter jobs={visibleJobs} rooms={data.rooms} preparationError={preparation.connectionError} onPreparation={id => { setTasks(false); preparation.open(id); }} onClose={() => setTasks(false)} onRetry={id => resourceAction(() => apiRequest(`/api/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }))} />}
    {preparation.selection?.open && <PreparationProgress key={`${user?.username}:${preparation.selection.id}`} task={preparation.selected} goal={preparation.selection.goal}
      submitting={preparation.submitting} submitError={preparation.submitError} connectionError={preparation.connectionError} controlError={preparation.controlError} controlling={preparation.controlling}
      onClose={preparation.close} onControl={preparation.control} onEnter={async id => {
        const course = await apiRequest<Room>(pathFor(id));
        commit({ ...current.current, rooms: [...current.current.rooms.filter(r => r.id !== id), course] });
        preparation.close(); location.hash = `/classroom/${encodeURIComponent(id)}`;
      }} />}
  </div>;
}
