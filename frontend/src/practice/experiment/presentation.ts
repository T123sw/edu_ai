import layoutScript from './frameLayout.js?raw';
import layoutCss from './frameLayout.css?raw';
import mathScript from './frameMath.js?raw';

/** Apply a common reading order without changing the saved scientific artifact. */
export function presentExperimentPage(html: string): string {
  const styles = `<style data-edu-frame-layout>${layoutCss}</style>`;
  const script = `<script data-edu-frame-layout>${`${layoutScript}\n${mathScript}`.replace(/<\/script/gi, '<\\/script')}</script>`;
  return html.replace(/<\/head\s*>/i, `${styles}</head>`).replace(/<\/body\s*>/i, `${script}</body>`);
}
