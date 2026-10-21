import { useEffect, useId, useRef, useState } from 'react';
import { ThemeAppearanceSettings } from './ThemeAppearanceSettings';
import './themeSwitcher.css';

export function ThemeSwitcher() {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  function closeAndFocus() { setOpen(false); trigger.current?.focus(); }

  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus();
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);

  return <div className="theme-switcher" ref={root} onKeyDown={event => {
    if (open && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeAndFocus(); }
  }} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
  }}>
    <button className="theme-switcher-trigger" ref={trigger} type="button" aria-label="页面配色" title="切换系统配色" aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? panelId : undefined} onClick={() => setOpen(value => !value)}>
      <svg className="theme-switcher-palette" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
        <path d="M12 3a9 9 0 1 0 0 18h1.1a2.3 2.3 0 0 0 1.6-3.9 1.4 1.4 0 0 1 1-2.4h2A3.3 3.3 0 0 0 21 11.4 8.6 8.6 0 0 0 12 3Z" fill="var(--panel-surface, #fffef9)" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <circle cx="7.1" cy="10.4" r="1.5" fill="#729466" />
        <circle cx="10.4" cy="6.9" r="1.5" fill="#6d9fb7" />
        <circle cx="15.2" cy="7.4" r="1.5" fill="#dba464" />
        <circle cx="17.7" cy="11.2" r="1.4" fill="#bd817c" />
      </svg>
    </button>
    {open && <div className="theme-switcher-panel" id={panelId} role="dialog" aria-label="页面配色"><ThemeAppearanceSettings onSelect={closeAndFocus} /></div>}
  </div>;
}
