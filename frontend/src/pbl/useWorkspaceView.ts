import { useEffect, useState } from 'react';

export type WorkspaceView = 'split' | 'code' | 'result';
const compactQuery = '(max-width: 900px)';

export function scrollToWorkspaceSection(target: HTMLElement | null) {
  if (!target) return;
  const main = target.closest<HTMLElement>('.pbl-main');
  if (!main) return;
  const container = getComputedStyle(main).overflowY === 'visible' ? main.parentElement! : main;
  const inset = main.querySelector('.pbl-section-nav')!.getBoundingClientRect().height + 8;
  container.scrollTo({top: container.scrollTop + target.getBoundingClientRect().top - container.getBoundingClientRect().top - inset});
}

export function useWorkspaceView() {
  const [requested, setView] = useState<WorkspaceView>('split');
  const [compact, setCompact] = useState(() => window.matchMedia(compactQuery).matches);
  useEffect(() => {
    const media = window.matchMedia(compactQuery);
    const update = () => setCompact(media.matches);
    update(); media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const view = compact && requested === 'split' ? 'code' : requested;
  return {view, setView, compact};
}
