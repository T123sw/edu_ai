const ABSOLUTE_URL_RE = /^https?:\/\//i;
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1']);

function getConfiguredApiBaseUrl(): string {
  const configured =
    typeof import.meta !== 'undefined' ? String((import.meta as any).env?.VITE_API_BASE_URL || '').trim() : '';
  return configured;
}

function getBrowserOrigin(): string {
  if (typeof window === 'undefined' || !window.location?.origin) {
    return '';
  }
  return String(window.location.origin || '').trim();
}

function getAssetBaseUrl(): string {
  const configured = getConfiguredApiBaseUrl();
  if (configured) {
    return configured;
  }
  const browserOrigin = getBrowserOrigin();
  if (browserOrigin && !LOOPBACK_HOSTS.has(String(window.location?.hostname || '').trim())) {
    return browserOrigin;
  }
  return 'http://127.0.0.1:8001';
}

function rewriteLoopbackAbsoluteUrl(value: string): string {
  if (typeof window === 'undefined') {
    return value;
  }
  try {
    const url = new URL(value);
    if (!LOOPBACK_HOSTS.has(url.hostname)) {
      return value;
    }

    const currentHostname = String(window.location?.hostname || '').trim();
    const targetBase =
      getConfiguredApiBaseUrl() ||
      (LOOPBACK_HOSTS.has(currentHostname) ? 'http://127.0.0.1:8001' : getBrowserOrigin());
    if (!targetBase) {
      return value;
    }
    return new URL(`${url.pathname}${url.search}${url.hash}`, targetBase).toString();
  } catch {
    return value;
  }
}

export function resolvePptAssetUrl(value: unknown): string | undefined {
  const text = String(value || '').trim();
  if (!text) {
    return undefined;
  }
  if (ABSOLUTE_URL_RE.test(text)) {
    return rewriteLoopbackAbsoluteUrl(text);
  }
  const baseUrl = getAssetBaseUrl();
  if (text.startsWith('/')) {
    return `${baseUrl}${text}`;
  }
  return `${baseUrl}/${text.replace(/^\/+/, '')}`;
}
