const ABSOLUTE_URL_RE = /^https?:\/\//i;
const AUTH_STORAGE_KEY = 'edu-ai-auth';

function getBackendBaseUrl(): string {
  return (
    (typeof import.meta !== 'undefined' ? String((import.meta as any).env?.VITE_API_BASE_URL || '').trim() : '')
    || 'http://localhost:8000'
  );
}

export function getTeacherAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) {
      return null;
    }
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || null;
  } catch {
    return null;
  }
}

export function resolveGameHtmlUrl(value: unknown): string | undefined {
  const text = String(value || '').trim();
  if (!text) {
    return undefined;
  }
  if (ABSOLUTE_URL_RE.test(text)) {
    return text;
  }
  const baseUrl = getBackendBaseUrl().replace(/\/+$/, '');
  if (text.startsWith('/')) {
    return `${baseUrl}${text}`;
  }
  return `${baseUrl}/${text.replace(/^\/+/, '')}`;
}
