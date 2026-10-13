import { serialPolling } from './serialPolling';
import { refreshLearningState, type LiveLearningState as State } from './stateRefresh';
import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiRequest } from '../stitch/api/client';
import { courseMaterialToMarkdown } from '../stitch/api/courses';
import type { CourseMaterial } from '../stitch/api/types';
import { Home } from '../selfLearning/Home';
import { SpaceNavigation, InterviewEntry } from '../selfLearning/SpaceNavigation';
import { Research } from '../selfLearning/Research';
import { researchHref } from '../selfLearning/research';
import { Classroom } from '../selfLearning/Classroom';
import { ResourceCenter } from '../selfLearning/Library';
import { Brand, Empty, Icon, Modal } from '../selfLearning/ui';
import { uid, type Classroom as Room, type LearningState, type LearningResource } from '../selfLearning/model';
import '../selfLearning/styles.css';
import '../selfLearning/review.css';
import './live.css';
import '../selfLearning/space.css';
import { TaskCenter, TaskLauncher } from './TaskCenter';

import { PreparationNotifications } from './PreparationNotifications';
import { PreparationOptionsForm, PreparationTasks, defaultOptions, submitPreparation } from './Preparation';

const base = '/api/self-learning';
const pathFor = (id: string) => `${base}/courses/${encodeURIComponent(id)}`;
const empty: State = { version: 1, rooms: [], resources: [], jobs: [], shared: [], serverJobs: [] };
export default function LiveApp() {
  const { user } = useAuth();
  const [data, update] = useState<State>(empty);
  const current = useRef(data);
  const [hash, setHash] = useState(location.hash);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [tasks, setTasks] = useState(false);
  const [publish, setPublish] = useState(false);
  const pending = useRef(new Map<string, Record<string, unknown>>());
  const saveTimer = useRef<ReturnType<typeof setTimeout>>();
  const saving = useRef<Promise<void> | null>(null);
  const revision = useRef(0);
  const questions = useRef(new Map<string, string>());
  const [preparationOptions, setPreparationOptions] = useState(defaultOptions);
  const [preparationRevision, setPreparationRevision] = useState(0);
  const [preparationUploading, setPreparationUploading] = useState(false);
  const [path, raw = ''] = hash.replace(/^#/, '').split('?');
  const query = new URLSearchParams(raw);
  const home = !path || path === '/';
  const research = path === '/research';
  const interview = path === '/interview';
  const hub = home || research || interview;
  const library = path === '/resources';
  const roomId = path?.startsWith('/classroom/') ? path.slice(11) : query.get('classroom');
  const room = data.rooms.find(r => r.id === roomId);
  const commit = useCallback((value: State) => { current.current = value; update(value); }, []);
  const refresh = useCallback(async () => {
    const started = revision.current;
    const activeId = location.hash.split('?')[0].replace('#/classroom/', '');
    const value = await refreshLearningState(current.current, activeId);
    if (started === revision.current && !pending.current.size && !saving.current) {
      const activeId = location.hash.split('?')[0].replace('#/classroom/', '');
      value.rooms = value.rooms.map(next => { const previous = current.current.rooms.find(r => r.id === next.id);
        return next.id === activeId && previous?.manifestRef && next.manifestRef?.version !== previous.manifestRef.version ? previous : next; });
      commit(value);
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
      if (before.selectedId !== after.selectedId) patch.selectedId = after.selectedId;
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
      if (!pending.current.size && !saving.current) {
        await refresh().catch(c => active && setError(c.message)).finally(() => active && setLoading(false));
      }
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
  const open = async (target: Room, shared = false) => action(async () => {
    if (shared) await apiRequest(`${pathFor(target.id)}/join`, { method: 'POST' });
    else await apiRequest(`${pathFor(target.id)}/learning`, { method: 'PATCH', body: '{}' });
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
  return <div className={`sl-app sl-live frontend-review sl-space-shell ${hub ? 'sl-space-index' : 'in-course-workspace'} ${room && path?.startsWith('/classroom/') ? 'in-classroom' : ''}`} onClickCapture={e => {
    const link = (e.target as Element).closest('a');
    if (link && /^\?(liveWorkbench|account)=/.test(link.getAttribute('href') || '')) { e.preventDefault(); void action(async () => { location.assign(link.href); }); }
  }}>
    <header className={hub ? 'sl-space-header' : 'sl-header'}>
      {hub ? <SpaceNavigation active={research ? 'research' : interview ? 'interview' : 'home'} /> : <><a href="#/" aria-label="返回首页"><Brand /></a><span className="sl-live-title">{room?.title}</span><nav className="sl-main-nav" aria-label="主导航"><a className={!library ? 'active' : ''} href={room ? `#/classroom/${room.id}` : '#/'}>AI 课堂</a><a href={researchHref(room)}>科研实践</a><a href={workbench()}>工作台</a><a className={library ? 'active' : ''} href={`#/resources${room ? '?classroom=' + room.id : ''}`}>资源中心</a></nav></>}
      <div className="sl-live-account"><PreparationNotifications key={user?.username} owner={user?.username || ''} /><TaskLauncher jobs={data.serverJobs} open={tasks} onClick={() => setTasks(true)} /><a className="sl-avatar" aria-label="个人中心" title={user?.username} href="?account=1#profile">{user?.username.slice(0, 1)}</a></div>
    </header>
    {error && <div className="sl-live-error" role="alert">{error}<button onClick={() => void action(async () => { await flush(); await refresh(); })}>刷新状态</button><button aria-label="关闭提示" onClick={() => setError('')}>×</button></div>}
    {busy && <div className="sl-live-busy" role="status">{busy}</div>}
    {loading ? <p className="sl-auth-loading" role="status">正在读取学习空间…</p> : home ? <Home live canCreateFromUploads={preparationOptions.uploads.length > 0 || preparationUploading} preparationOptions={<PreparationOptionsForm value={preparationOptions} onChange={setPreparationOptions} onUploadingChange={setPreparationUploading} />} preparationTasks={<PreparationTasks key={user?.username} owner={user?.username || ''} refreshKey={preparationRevision} />} rooms={data.rooms} shared={data.shared} canPublish={user?.role === 'teacher' || user?.role === 'admin'} onOpen={(r, shared) => void open(r, shared)} onPublish={() => setPublish(true)} onCreate={text => {
      if (busy) return;
      if (preparationUploading) { setError('资料仍在上传，请完成后再开始学习'); return; }
      void action(async () => { await submitPreparation(user!.username, text, preparationOptions); setPreparationRevision(v => v + 1); }, '正在提交课程准备任务…');
    }} /> : research ? <Research key={`${user?.username}:${raw}`} owner={`live:${user?.username}`} rooms={data.rooms} query={query} /> : interview ? <InterviewEntry /> : library ? <ResourceCenter room={room} classroomId={room?.id} resources={data.resources} resourceId={query.get('resource') || undefined} workbenchHref={workbench()} workbenchForResource={id => workbench(byId(id))}
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
    }} /> : <Empty title="课堂未找到" text="课堂不存在或当前账号无权访问。" action={<a href="#/">返回首页</a>} />}
    {tasks && <TaskCenter jobs={data.serverJobs} rooms={data.rooms} onClose={() => setTasks(false)} onRetry={id => resourceAction(() => apiRequest(`/api/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }))} />}
    {publish && <Modal title="共享我的课堂" onClose={() => setPublish(false)}><div className="sl-live-jobs"><p>共享后，其他用户可以加入并学习已发布的课堂内容。</p>{data.rooms.filter(r => r.canPublish).map(r => <button key={r.id} className="sl-secondary-button" onClick={() => void action(async () => { await apiRequest(`${pathFor(r.id)}/publish`, { method: 'POST' }); setPublish(false); })}>{r.title}<Icon name="upload" size={16} /></button>)}</div></Modal>}
  </div>;
}
