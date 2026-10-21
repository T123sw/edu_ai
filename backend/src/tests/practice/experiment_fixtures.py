"""Deterministic adapter fixtures, never selected by the production generator."""
import json
from pathlib import Path
from app.practice.experiment.contracts import ExperimentSpec, digest
from app.practice.native_runtime import wrap_native_html
ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = ROOT / 'backend/src/app/practice/skills/design-experiment/examples'
ADAPTERS = {
'quicksort': 's.selected=c.input.index;return s;',
'friction': 's.mu=c.input.mu;s.distance=s.velocity*s.velocity/(2*s.mu*9.8);return s;',
'probability': 'let seed=s.seed;s.samples=[];for(let i=0;i<c.input.count;i++){seed=(seed*1664525+1013904223)>>>0;s.samples.push(seed/2**32<.5?1:0)}s.seed=seed;s.count=s.samples.length;s.frequency=s.samples.reduce((a,b)=>a+b,0)/s.count;return s;',
}
def artifact(name):
    spec = ExperimentSpec.model_validate_json((EXAMPLES / f'{name}.json').read_text()).model_dump()
    raw = '''<!doctype html><html lang="zh-CN"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:20px;box-sizing:border-box;font:16px system-ui;background:#f7faf8}canvas{width:100%;height:380px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body><canvas aria-label="实验图"></canvas><pre id="state"></pre><script>
let current={},policy={allowed_actions:[]};const canvas=document.querySelector('canvas');
function draw(){const w=canvas.clientWidth,h=380;canvas.width=w*devicePixelRatio;canvas.height=h*devicePixelRatio;const x=canvas.getContext('2d');x.scale(devicePixelRatio,devicePixelRatio);x.clearRect(0,0,w,h);x.font='16px system-ui';x.fillStyle='#254b3b';x.fillText('观察本次操作的变化',12,30);if(current.array){current.array.forEach((v,i)=>{const bw=(w-30)/5;x.fillStyle=i===current.selected?'#de9a40':'#4d8b70';x.fillRect(10+i*bw,320-v*25,bw-8,v*25);x.fillText(String(v),10+i*bw,345)})}else{x.fillText('当前结果：'+(current.distance??current.frequency??'等待操作'),12,110)}}
new ResizeObserver(draw).observe(canvas);
canvas.addEventListener('click',e=>{if(current.array && policy.allowed_actions.includes('select')&&!policy.busy){const rect=canvas.getBoundingClientRect();const index=Math.min(4,Math.max(0,Math.floor((e.clientX-rect.left-10)/((canvas.clientWidth-30)/5))));void EduExperiment.dispatch('select',{index});}});
EduExperiment.register({apply(s,c){__APPLY__},render(s,p){policy=p;current=s;document.querySelector('#state').textContent=JSON.stringify(s);draw()}});
</script></body></html>'''.replace('__APPLY__', ADAPTERS[name])
    package = {'protocol': 'edu-experiment/1', 'revision': digest(spec), 'spec': spec, 'teaching': {'status': 'reserved'}}
    return {'html': wrap_native_html(raw, experiment=package), 'experiment': package, 'plan': {'concept_name': spec['title'], 'concept_overview': spec['overview'], 'steps': [{'title': '演示', 'instruction': '观察', 'question': '为什么？'}]}, 'presentation': 'maic-ui-native-v1'}
if __name__ == '__main__':
    folder = ROOT / '.runtime/experiment-fixtures'; folder.mkdir(exist_ok=True, parents=True)
    for name in ADAPTERS: (folder / f'{name}.json').write_text(json.dumps(artifact(name), ensure_ascii=False))
