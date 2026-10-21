// Saved pages always bundle KaTeX, but generated pages may omit its initializer.
// Render reference prose independently of the generated script's detection logic.
(() => {
  const start = () => {
    if (typeof window.renderMathInElement !== 'function') return;
    const selector = '.edu-frame-reference,[data-experiment-region="reference"]';
    const roots = [...document.querySelectorAll(selector)]
      .filter(el => !el.parentElement?.closest(selector));
    const options = {
      throwOnError: false,
      strict: false,
      trust: false,
      ignoredClasses: ['katex', 'katex-display', 'katex-error'],
      ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option', 'input', 'select', 'button'],
    };
    const observe = () => roots.forEach(root => observer.observe(root, {
      childList: true, characterData: true, subtree: true,
    }));
    const render = () => {
      // Do not observe our own replacements or repeatedly parse rendered math.
      observer.disconnect();
      try {
        roots.forEach(root => window.renderMathInElement(root, options));
      } finally {
        observe();
      }
    };
    const observer = new MutationObserver(render);
    render();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
