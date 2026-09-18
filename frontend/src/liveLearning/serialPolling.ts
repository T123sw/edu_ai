export function serialPolling(load: (signal: AbortSignal) => Promise<unknown>, delay: number) {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const poll = async () => {
    try { await load(controller.signal); }
    finally { if (!controller.signal.aborted) timer = setTimeout(() => void poll(), delay); }
  };
  void poll();
  return () => { controller.abort(); clearTimeout(timer); };
}
