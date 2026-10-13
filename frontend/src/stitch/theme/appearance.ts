import { useSyncExternalStore } from 'react';

export const themeNames = ['forest', 'ocean', 'sunset', 'dark', 'system'] as const;
export type ThemeName = typeof themeNames[number];
export type ResolvedTheme = Exclude<ThemeName, 'system'>;
export const themeStorageKey = 'stitch-theme';

export function parseTheme(value: unknown): ThemeName {
  return themeNames.includes(value as ThemeName) ? value as ThemeName : 'forest';
}
export function resolveTheme(theme: ThemeName, prefersDark: boolean): ResolvedTheme {
  return theme === 'system' ? (prefersDark ? 'dark' : 'forest') : theme;
}

let preference: ThemeName = 'forest';
let initialized = false;
const subscribers = new Set<() => void>();
let systemScheme: MediaQueryList | undefined;

function readPreference() {
  try { return parseTheme(window.localStorage.getItem(themeStorageKey)); }
  catch { return preference; }
}
function applyTheme() {
  document.documentElement.dataset.theme = resolveTheme(preference, !!systemScheme?.matches);
  document.documentElement.dataset.themePreference = preference;
  subscribers.forEach(notify => notify());
}
/** One observer per document, including embedded reports and classroom players. */
export function initializeAppearance() {
  if (initialized || typeof window === 'undefined') return;
  initialized = true;
  preference = readPreference();
  systemScheme = window.matchMedia('(prefers-color-scheme: dark)');
  systemScheme.addEventListener('change', () => {
    if (preference === 'system') applyTheme();
  });
  window.addEventListener('storage', event => {
    if (event.key !== themeStorageKey && event.key !== null) return;
    preference = readPreference();
    applyTheme();
  });
  applyTheme();
}
export function setTheme(theme: ThemeName) {
  initializeAppearance();
  preference = parseTheme(theme);
  try { window.localStorage.setItem(themeStorageKey, preference); }
  catch { /* Keep switching usable when browser storage is unavailable. */ }
  applyTheme();
}
const subscribe = (notify: () => void) => {
  subscribers.add(notify);
  return () => { subscribers.delete(notify); };
};
export function useAppearance() {
  initializeAppearance();
  const theme = useSyncExternalStore(subscribe, () => preference, () => 'forest' as ThemeName);
  return [theme, setTheme] as const;
}
