/** Presentation-only wrapper: the generated experiment and its runtime stay intact. */
export function practiceDocument(html: string, native = false): string {
  // Keep native code, canvas coordinates and event listeners intact. Reflow
  // its two-panel document for the center column without scaling the bitmap.
  if (native) {
    // Native generators commonly name their logical drawing height explicitly.
    // Increase that source dimension, so redraws allocate matching DPR pixels
    // and calculate bar positions correctly instead of stretching a bitmap.
    html = html.replace(/^(\s*const\s+(?:CANVAS_CSS_HEIGHT|CANVAS_HEIGHT)\s*=\s*)(\d+)(\s*;)/gm,
      (_, prefix: string, value: string, suffix: string) => `${prefix}${Math.max(560, Number(value))}${suffix}`);
    const styles = `<style data-practice-native-presentation>
html,body{min-height:100%;margin:0}
body>main{max-width:none!important;padding:16px!important}
[data-practice-native-heading]{display:none!important}
.edu-practice-native-layout{display:block!important;min-width:0}
.edu-practice-native-simulation{width:100%!important;max-width:none!important;min-width:0!important;box-sizing:border-box!important}
[data-practice-native-display]{min-height:560px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center}
[data-practice-native-config]{margin-top:24px!important;padding-top:20px;border-top:1px solid #dce5e1}
details[data-practice-native-notes]{margin-top:20px;border-top:1px solid #dce5e1;padding-top:12px}
details[data-practice-native-notes]>summary{cursor:pointer;font:500 14px/1.6 system-ui,sans-serif;color:#536d64;padding:8px 0}
details[data-practice-native-notes]>:not(summary){margin-top:12px}
</style>`;
    const layout = `<script data-practice-native-presentation>
(()=>{
  document.addEventListener('keydown',event=>{if(event.key==='Escape')parent.postMessage({type:'edu-practice-exit-focus'},'*')});
  const arrange=()=>{
    for(const heading of document.querySelectorAll('body>header,body>main>header')){
      if(heading.querySelector('h1')&&!heading.querySelector('button,input,select,textarea,a,[data-action]'))heading.dataset.practiceNativeHeading='';
    }
    const visual=document.querySelector('.simulation-panel');
    if(visual){
      const canvas=visual.querySelector('canvas');
      const display=canvas&&canvas.parentElement;
      if(display&&display!==visual&&!display.querySelector('[data-param],[data-action]'))display.dataset.practiceNativeDisplay='';
      const parameter=visual.querySelector('[data-param]');
      const config=parameter&&[...visual.children].find(element=>element.contains(parameter));
      if(config&&!config.querySelector('canvas'))config.dataset.practiceNativeConfig='';
    }
    const run=document.querySelector('[data-action="run"]');
    let steps=document.querySelector('.process-panel,#stepList');
    if(!run||!steps||steps.contains(run))return;
    while(steps.parentElement&&!steps.parentElement.contains(run))steps=steps.parentElement;
    const container=steps.parentElement;
    if(!container||container===document.body||container===document.documentElement||steps.contains(run))return;
    const simulation=[...container.children].find(element=>element.contains(run));
    if(!simulation||simulation===steps||steps.querySelector('canvas,[data-param],[data-action]'))return;
    const notes=document.createElement('details');notes.dataset.practiceNativeNotes='';
    const summary=document.createElement('summary');summary.textContent='实验说明与原始步骤';notes.append(summary);
    container.classList.add('edu-practice-native-layout');simulation.classList.add('edu-practice-native-simulation');
    notes.append(steps);container.append(notes);
    window.dispatchEvent(new Event('resize'));
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',arrange,{once:true});else arrange();
})();
</script>`;
    return html.replace(/<\/head\s*>/i, () => `${styles}</head>`).replace(/<\/body\s*>/i, () => `${layout}</body>`);
  }
  const styles = `<style data-practice-presentation>
html,body{min-height:0!important;height:auto!important;background:#fff!important;color-scheme:light;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif!important}
body{box-sizing:border-box!important;margin:0!important;padding:18px!important;font-size:14px;line-height:1.6}
body>:is(main,.wrap,.wrapper,.container,#app){max-width:none!important;width:100%;box-sizing:border-box}
button,input,select,textarea{font-family:inherit!important}button{cursor:pointer}input[type=range]{accent-color:#17877e}input[type=number],select{min-height:34px;border-radius:7px;padding:5px 8px}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #218c83;outline-offset:3px}
canvas,svg{max-width:100%}h1{font-size:21px!important;line-height:1.4!important;margin-top:0!important}h2{line-height:1.5}
</style>`;
  const resize = `<script data-practice-presentation>
(()=>{let pending=false,last=0;const measure=()=>{pending=false;const b=document.body;if(!b)return;const h=Math.ceil(Math.max(b.getBoundingClientRect().height,b.scrollHeight));if(h>0&&Math.abs(last-h)>2){last=h;parent.postMessage({type:'edu-practice-size',height:h},'*')}};const schedule=()=>{if(!pending){pending=true;requestAnimationFrame(measure)}};const init=()=>{new ResizeObserver(schedule).observe(document.body);schedule();setTimeout(schedule,250)};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();window.addEventListener('resize',schedule);window.addEventListener('load',schedule);document.addEventListener('keydown',event=>{if(event.key==='Escape')parent.postMessage({type:'edu-practice-exit-focus'},'*')})})();
</script>`;
  const styled = html.replace(/<\/head\s*>/i, () => `${styles}</head>`);
  return styled.replace(/<\/body\s*>/i, () => `${resize}</body>`);
}
