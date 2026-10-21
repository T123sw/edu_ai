"""An opaque-origin, offline runtime shared by validation and the learner player."""
import re

CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
BRIDGE = '''<script>
(()=>{
 let results = {}, timer = null;
 const snapshot = () => ({parameters:Object.fromEntries(Array.from(document.querySelectorAll('[data-param]')).map(e=>[e.dataset.param,e.type==='checkbox'?e.checked:e.value])),results});
 const send = () => parent.postMessage({type:'edu-practice-state',state:snapshot()},'*');
 const schedule = () => {if(timer===null)timer=setTimeout(()=>{timer=null;send()},500)};
 window.EduPractice={report(value){if(value && typeof value==='object') results=JSON.parse(JSON.stringify(value,(_,v)=>typeof v==='number'&&!Number.isFinite(v)?String(v):v));schedule()},snapshot};
 document.addEventListener('input',schedule);
 document.addEventListener('change',schedule);
 document.addEventListener('click',schedule);
 window.addEventListener('error',e=>parent.postMessage({type:'edu-practice-error',message:String(e.message).slice(0,300)},'*'));
 window.addEventListener('unhandledrejection',()=>parent.postMessage({type:'edu-practice-error',message:'实验运行发生异常，请重置或重新生成'},'*'));
 window.addEventListener('DOMContentLoaded',()=>setTimeout(send,250));
})();
</script>'''

def wrap_html(raw: str) -> str:
    start = re.search(r'<!doctype\s+html|<html\b', raw, re.I)
    end = raw.lower().rfind('</html>')
    if not start or end < 0 or len(raw) > 180000:
        raise ValueError('模型没有返回完整的实验页面')
    html = raw[start.start():end + 7]
    if not re.search(r'<head(?:\s[^>]*)?>', html, re.I):
        raise ValueError('实验页面缺少 head')
    # CSP must precede any generated markup. External content is intentionally blocked.
    html = re.sub(r'<meta\b[^>]*http-equiv\s*=\s*[\'\"]?refresh\b[^>]*>', '', html, flags=re.I)
    return re.sub(r'(<head(?:\s[^>]*)?>)', lambda m: m[0] + '<meta http-equiv="Content-Security-Policy" content="' + CSP + '">' + BRIDGE, html, count=1, flags=re.I)
