// Presentation only: preserve generated IDs, handlers, controls and experiment state.
(() => {
  const arrange = () => {
    let teachingSlot;
    const interactive = 'button,input,select,textarea,[contenteditable="true"]';
    const visual = document.querySelector('[data-experiment-region="visual"]') || document.querySelector('canvas') ||
      [...document.querySelectorAll('svg')].find(el => Number(el.getAttribute('width')) > 160 || el.getBoundingClientRect().width > 160);
    const block = visual?.matches('[data-experiment-region="visual"]') ? visual : visual?.closest('section') || visual?.parentElement;
    const root = block?.parentElement;
    if (root && root !== document.documentElement && root.children.length > 1) {
      document.body.classList.add('edu-frame-layout');
      root.classList.add('edu-frame-root');
      block.classList.add('edu-frame-visual');
      let references;
      const reference = el => {
        if (!references) {
          references = document.createElement('details');references.className = 'edu-frame-reference';
          const summary = document.createElement('summary');summary.textContent = '原理与公式';
          references.append(summary);root.append(references);
          references.addEventListener('toggle', () => window.dispatchEvent(new Event('resize')));
        }
        // Generated reference regions may already contain a disclosure. Keep
        // one fold so opening the host disclosure reveals the actual content.
        const folds = [...el.querySelectorAll('details')];
        if (el.matches('details')) folds.unshift(el);
        for (const fold of folds) {
          fold.open = true;
          fold.classList.add('edu-frame-reference-content');
        }
        references.append(el);
      };
      for (const el of [...root.children]) {
        if (el === block || el === references || el.matches('script,style')) continue;
        if (el.matches('header') && el.querySelector('h1') && !el.querySelector(interactive)) {
          el.classList.add('edu-frame-heading');continue;
        }
        const kind = el.getAttribute('data-experiment-region');
        if (!el.querySelector(interactive) && (kind === 'reference' || el.querySelector('.katex,math') || /\\\(|\\\[/.test(el.textContent))) {
          reference(el);continue;
        }
        el.classList.add('edu-frame-section');
        if (el.querySelector(interactive) || el.matches('form')) el.classList.add('edu-frame-controls');
        else if (getComputedStyle(el).display === 'grid') el.classList.add('edu-frame-metrics');
      }
      teachingSlot = document.createElement('div');
      teachingSlot.className = 'edu-frame-teaching-slot';
      teachingSlot.setAttribute('aria-hidden', 'true');
      block.after(teachingSlot);
      window.addEventListener('message', event => {
        if (event.source !== parent || event.data?.type !== 'edu-experiment-teaching-size') return;
        const visualHeight = event.data.visualHeight;
        if (Number.isFinite(visualHeight) && visualHeight >= 160 && visualHeight <= 420) document.documentElement.style.setProperty('--edu-visual-height', visualHeight + 'px');
        const height = event.data.height;
        if (Number.isFinite(height) && height > 0 && height < 10000) teachingSlot.style.height = Math.ceil(height) + 'px';
      });
      // Keep the source's drawing logic responsible for canvas resolution and labels.
      window.dispatchEvent(new Event('resize'));
    }
    let pending = false, previous = 0, previousWidth = 0, previousTop;
    const report = () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        const width = document.body.getBoundingClientRect().width;
        if (!width) return;
        if (width !== previousWidth) {
          previousWidth = width;window.dispatchEvent(new Event('resize'));
        }
        const elements = [...document.body.children].filter(el => !el.matches('script,style') && el.getBoundingClientRect().height);
        const height = Math.ceil(Math.max(0, ...elements.map(el => el.getBoundingClientRect().bottom + window.scrollY)) + 20);
        const teachingTop = teachingSlot ? Math.ceil(teachingSlot.getBoundingClientRect().top + window.scrollY) : undefined;
        if (height !== previous || teachingTop !== previousTop) {
          previous = height; previousTop = teachingTop;
          parent.postMessage({type:'edu-experiment-layout',height,teachingTop}, '*');
        }
      });
    };
    new ResizeObserver(report).observe(document.body);
    window.addEventListener('resize',report);report();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrange, {once:true});
  else arrange();
})();
