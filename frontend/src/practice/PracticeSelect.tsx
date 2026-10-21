import { useEffect, useId, useRef, useState } from 'react';
import { Icon } from '../selfLearning/ui';
import './practiceFocusSelect.css';

type PracticeSelectOption = { value: string; label?: string; description: string };

export function PracticeSelect({ label, options, value, onChange }: {
  label: string;
  options: readonly PracticeSelectOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [placement, setPlacement] = useState({ above: false, maxHeight: 300 });
  function show(index = Math.max(0, options.findIndex(option => option.value === value))) {
    const box = trigger.current?.getBoundingClientRect();
    if (box) {
      const below = window.innerHeight - box.bottom - 24;
      const above = box.top - 24;
      const useAbove = below < 270 && above > below;
      setPlacement({ above: useAbove, maxHeight: Math.max(80, Math.min(300, useAbove ? above : below)) });
    }
    setActive(index); setOpen(true);
  }
  function choose(index: number) { onChange(options[index].value); setOpen(false); }
  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const resize = () => setOpen(false);
    document.addEventListener('pointerdown', dismiss);
    window.addEventListener('resize', resize);
    return () => { document.removeEventListener('pointerdown', dismiss); window.removeEventListener('resize', resize); };
  }, [open]);
  useEffect(() => {
    if (open) document.getElementById(`${id}-option-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active, id]);
  return <div ref={root} className="sl-focus-select" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <button ref={trigger} type="button" className="sl-focus-trigger" role="combobox" aria-label={label} aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-list`} aria-activedescendant={open ? `${id}-option-${active}` : undefined}
      onClick={() => open ? setOpen(false) : show()}
      onKeyDown={event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          if (!open) show(); else setActive(index => (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length);
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault(); show(event.key === 'Home' ? 0 : options.length - 1);
        } else if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault(); if (open) choose(active); else show();
        } else if (event.key === 'Escape' && open) {
          event.preventDefault(); event.stopPropagation(); setOpen(false);
        } else if (event.key === 'Tab') setOpen(false);
      }}>
      <svg className="sl-focus-icon" viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true"><path d="M3 6h14M3 14h14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><circle cx="7" cy="6" r="2" fill="var(--edu-paper, #f3f4eb)" stroke="currentColor" strokeWidth="1.3" /><circle cx="13" cy="14" r="2" fill="var(--edu-paper, #f3f4eb)" stroke="currentColor" strokeWidth="1.3" /></svg>
      <span className="sl-focus-label">{label}</span><span className="sl-focus-value">{options.find(option => option.value === value)?.label || value}</span><span className="sl-focus-chevron"><Icon name="chevron" size={13} /></span>
    </button>
    {open && <div className={`sl-focus-menu${placement.above ? ' opens-above' : ''}`} style={{ maxHeight: placement.maxHeight }}>
      <div className="sl-focus-menu-heading" id={`${id}-label`}>选择{label}</div>
      <ul id={`${id}-list`} role="listbox" aria-labelledby={`${id}-label`}>
        {options.map((option, index) => <li key={option.value} id={`${id}-option-${index}`} role="option" aria-selected={value === option.value} className={active === index ? 'is-active' : ''} onPointerMove={() => setActive(index)} onMouseDown={event => event.preventDefault()} onClick={() => choose(index)}>
          <span><strong>{option.label || option.value}</strong><small>{option.description}</small></span>
          {value === option.value && <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m4 10 4 4 8-8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>}
        </li>)}
      </ul>
    </div>}
  </div>;
}
