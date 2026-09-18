// Offering a quiz check and reading its saved attempts is one bounded load.
// Large quizzes must not flood the browser connection pool on mount.
let running = 0;
const waiting: (() => void)[] = [];
export async function loadCheck<T>(load: () => Promise<T>): Promise<T> {
  await new Promise<void>(resolve => {
    const start = () => { running++; resolve(); };
    if (running < 3) start(); else waiting.push(start);
  });
  try { return await load(); }
  finally { running--; waiting.shift()?.(); }
}
