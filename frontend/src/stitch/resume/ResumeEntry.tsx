import { useEffect, useRef, useState } from 'react';
import { useAuthSession } from '../authSession';
import { readResume, resumeHash, resumeKey, saveResume } from './resumeRecord';
import { validateResume, type ResumeResult } from './validateResume';
import { resumeApi } from './resumeApi';
import './resume.css';

export function ResumeEntry({ refreshToken = 0 }: { refreshToken?: number }) {
  const { user, authenticated } = useAuthSession();
  const identity = authenticated && user ? resumeKey(user) : '';
  const [state, setState] = useState<{ identity: string; result: ResumeResult | null; busy: boolean }>({ identity: '', result: null, busy: false });
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const request = ++generation.current;
    if (!user || !authenticated) return;
    const record = readResume(user);
    if (!record) { setState({ identity, result: null, busy: false }); return; }
    setState({ identity, result: null, busy: true });
    void validateResume(user, record, resumeApi).then((result) => {
      if (generation.current !== request) return;
      if (result.status === 'invalid') saveResume(user, null);
      setState({ identity, result, busy: false });
    });
    // Invalidate both the initial lookup and any later click lookup on unmount.
    const invalidate = () => { generation.current += 1; };
    return invalidate;
  }, [user, authenticated, identity, retry, refreshToken]);
  if (!identity || state.identity !== identity) return null;
  const result = state.result;
  if (!state.busy && (!result || result.status === 'invalid')) return null;
  const action = user?.role === 'student' ? '继续学习' : '继续备课';
  async function resume() {
    if (!user || !result || (result.status !== 'valid' && result.status !== 'fallback')) return;
    const originHash = window.location.hash;
    const request = ++generation.current;
    setState((current) => ({ ...current, busy: true }));
    const checked = await validateResume(user, result.record, resumeApi);
    if (generation.current !== request || window.location.hash !== originHash) return;
    if (checked.status === 'invalid') saveResume(user, null);
    setState({ identity, result: checked, busy: false });
    if (checked.status !== 'valid' && checked.status !== 'fallback') return;
    if (checked.status === 'fallback' && result.status !== 'fallback') return;
    saveResume(user, checked.record);
    window.location.hash = resumeHash(user, checked.record);
  }
  return (
    <section className="resume-entry" aria-label={action} aria-busy={state.busy}>
      <span className="resume-entry__icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 5.5C9 3.5 5.5 3.5 3 4.5v14c2.5-1 6-1 9 1 3-2 6.5-2 9-1v-14c-2.5-1-6-1-9 1Z" />
          <path d="M12 5.5v14M6 8h3M6 11h3M15 8h3M15 11h3" />
        </svg>
      </span>
      <div className="resume-entry__text">
        <span className="resume-entry__eyebrow">{user?.role === 'student' ? '接着上次，继续学习' : '接着上次，继续备课'}</span>
        {result && (result.status === 'valid' || result.status === 'fallback') ? <>
          <span className="resume-entry__summary" title={[result.course.title, result.label].filter(Boolean).join(' · ')}>
            <strong>{result.course.title}</strong>
            {result.label ? <span> · {result.label}</span> : null}
          </span>
          {result.status === 'fallback' ? <small role="status">原位置已不可用，将返回本课程概览。</small> : null}
        </> : <span role="status">{state.busy ? '正在确认上次课程…' : '暂时无法确认上次课程，请重试。'}</span>}
      </div>
      <button type="button" disabled={state.busy} onClick={result?.status === 'retry' ? () => setRetry((value) => value + 1) : () => void resume()}>
        {state.busy ? '正在确认…' : result?.status === 'retry' ? '重试' : `${action} →`}
      </button>
    </section>
  );
}
