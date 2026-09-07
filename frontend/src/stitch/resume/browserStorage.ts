// Optional browser persistence must not prevent the application from rendering.
export const browserStorage = {
  getItem(key: string): string | null {
    try { return window.localStorage.getItem(key); } catch { return null; }
  },
  setItem(key: string, value: string): void {
    try { window.localStorage.setItem(key, value); } catch { /* Persistence unavailable. */ }
  },
  removeItem(key: string): void {
    try { window.localStorage.removeItem(key); } catch { /* Persistence unavailable. */ }
  },
};
