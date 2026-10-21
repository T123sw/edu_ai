import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { submitPreparation, type PreparationOptions } from './Preparation';
import { mergePreparationTasks, type PreparationTask } from './preparationProgress';
import { serialPolling } from './serialPolling';

type Selection = { id: string; goal: string; open: boolean };
const base = '/api/course-preparations';
const storageKey = (owner: string) => `preparation:progress:${owner}`;

export function usePreparationProgress(owner: string) {
  const [stateOwner, setStateOwner] = useState(owner);
  const [tasks, setTasks] = useState<PreparationTask[]>([]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [controlError, setControlError] = useState('');
  const [controlling, setControlling] = useState(false);
  const activeOwner = useRef(owner);
  activeOwner.current = owner;
  const submittingOwner = useRef<string | null>(null);
  const controllingOwner = useRef<string | null>(null);

  const remember = useCallback((next: Selection | null) => {
    setSelection(next);
    try {
      if (next?.id) localStorage.setItem(storageKey(owner), JSON.stringify(next));
      else localStorage.removeItem(storageKey(owner));
    } catch { /* Progress still works when browser storage is unavailable. */ }
  }, [owner]);

  useEffect(() => {
    setStateOwner(owner);
    setTasks([]); setSelection(null); setSubmitting(false); setSubmitError('');
    setConnectionError(''); setControlError(''); setControlling(false);
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey(owner)) || 'null');
      if (typeof saved?.id === 'string' && saved.id) {
        setSelection({ id: saved.id, goal: String(saved.goal || ''), open: saved.open === true });
      }
    } catch { /* Ignore malformed local state. */ }
    if (!owner) return;
    return serialPolling(async signal => {
      const controller = new AbortController();
      const abort = () => controller.abort();
      signal.addEventListener('abort', abort);
      const timeout = setTimeout(abort, 15000);
      try {
        const response = await apiRequest<{ preparations: PreparationTask[] }>(base, { signal: controller.signal });
        if (!signal.aborted && activeOwner.current === owner) {
          setTasks(previous => mergePreparationTasks(previous, response.preparations || []));
          setConnectionError('');
        }
      } catch {
        if (!signal.aborted && activeOwner.current === owner) setConnectionError('暂时无法获取最新进度，正在自动重连。任务可能仍在后台继续。');
      } finally {
        clearTimeout(timeout); signal.removeEventListener('abort', abort);
      }
    }, 3000);
  }, [owner]);

  const submit = async (goal: string, options: PreparationOptions) => {
    if (submittingOwner.current === owner) return;
    submittingOwner.current = owner;
    setSubmitting(true); setSubmitError(''); setControlError(''); setConnectionError('');
    remember({ id: '', goal, open: true });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const task = await submitPreparation(owner, goal, options, controller.signal);
      if (activeOwner.current !== owner) return;
      setTasks(previous => mergePreparationTasks(previous, [task]));
      // Keep a manually minimized window minimized while the POST is in flight.
      setSelection(previous => {
        const next = { id: task.preparation_id, goal, open: previous?.open ?? true };
        try { localStorage.setItem(storageKey(owner), JSON.stringify(next)); } catch { /* Optional persistence. */ }
        return next;
      });
    } catch (cause) {
      if (activeOwner.current === owner) setSubmitError(controller.signal.aborted
        ? '提交响应超时，任务可能已经接收。可关闭窗口查看后台任务，或用相同目标重新提交。'
        : cause instanceof Error ? cause.message : '提交未成功，请稍后重试。');
    } finally {
      clearTimeout(timeout);
      if (submittingOwner.current === owner) submittingOwner.current = null;
      if (activeOwner.current === owner) setSubmitting(false);
    }
  };

  const control = async (task: PreparationTask, action: 'cancel' | 'retry') => {
    if (controllingOwner.current === owner) return false;
    controllingOwner.current = owner;
    setControlling(true); setControlError('');
    try {
      const next = await apiRequest<PreparationTask>(`${base}/${encodeURIComponent(task.preparation_id)}/${action}`, {
        method: 'POST', body: JSON.stringify(action === 'cancel'
          ? task.attempt_no ? { expected_attempt_no: task.attempt_no } : { expected_revision: task.revision }
          : {}),
      });
      if (activeOwner.current === owner) setTasks(previous => mergePreparationTasks(previous, [next]));
      return true;
    } catch (cause) {
      if (activeOwner.current === owner) setControlError(cause instanceof Error ? cause.message : '操作未成功，请重试。');
      return false;
    } finally {
      if (controllingOwner.current === owner) controllingOwner.current = null;
      if (activeOwner.current === owner) setControlling(false);
    }
  };

  return {
    tasks: stateOwner === owner ? tasks : [], selection: stateOwner === owner ? selection : null,
    submitting, submitError, connectionError, controlling, controlError, submit, control,
    selected: stateOwner === owner ? tasks.find(task => task.preparation_id === selection?.id) : undefined,
    open: (id: string) => { setSubmitError(''); setControlError(''); remember({ id, goal: selection?.id === id ? selection.goal : '', open: true }); },
    close: () => remember(selection ? { ...selection, open: false } : null),
  };
}
