from app.practice.pages.contracts import package_spec, PROTOCOL
from app.practice.experiment.contracts import digest
from app.practice.native_runtime import wrap_native_html
PLAN = {'title':'相邻比较练习', 'overview':'比较与交换', 'demo_initial':'数组[3,1]', 'demo_result':{'count':1},
        'demo_steps':[{'title':'比较相邻元素','before':'观察3和1','operation':'比较','after':'3大于1，应交换'}],
        'tasks':[{'title':title,'initial':'数组[3,1]','prompt':'请选择交换','interaction':'交换或保持','completion':'选择交换','success':'正确，已交换','retry':'这里需要交换，请重试','hints':['左边比右边大']} for title in ['尝试交换','再次尝试']],
        'exploration_prompts':['改变数组观察变化']}
RAW = '''<!doctype html><html><head></head><body><svg width="200" height="60"><text x="10" y="30">实验图形</text></svg><pre id="state"></pre><button id="correct">交换</button><button id="wrong">保持</button><script>
let state={count:0};const phase=window.__stagePage.phase;
function draw(){document.querySelector('#state').textContent=JSON.stringify(state)}
for(const id of ['correct','wrong'])document.getElementById(id).hidden=phase==='demonstrate';
EduStage.register({initialize(index){state={count:0};draw();for(const id of ['correct','wrong'])document.getElementById(id).disabled=phase==='guided'&&index>=window.__stagePage.spec.tasks.length},snapshot(){return state},restore(s){state=s;draw()},next(index){state.count=index+1;draw()}});
document.getElementById('correct').onclick=()=>EduStage.perform('交换',{choice:'swap'},()=>{state.count++;draw();if(phase==='guided')return{verdict:'pass'}});
document.getElementById('wrong').onclick=()=>EduStage.perform('保持',{choice:'keep'},()=>{state.count=99;draw();return{verdict:'fail'}});
</script></body></html>'''
def artifact():
    spec=package_spec(PLAN,{'mechanism':['相邻比较交换']});revision=digest({'spec':spec,'html':RAW})
    pages={phase:wrap_native_html(RAW,stage_page={'phase':phase,'spec':spec,'revision':revision}) for phase in ['demonstrate','guided','explore']}
    return {'html':pages['demonstrate'],'plan':{'concept_name':PLAN['title'],'concept_overview':PLAN['overview'],'steps':[]},'experiment':{'protocol':PROTOCOL,'revision':revision,'spec':spec,'pages':pages,'teaching':{'status':'reserved'}}}

ACTION_PLAN = {'title':PLAN['title'], 'objective':PLAN['overview'], 'demo_initial':PLAN['demo_initial'],
               'demo_actions':[{'title':'连续比较','operation':'每次比较一次直到过程完成'}],
               'tasks':[{k:t[k] for k in ('title','initial','interaction','completion')} for t in PLAN['tasks']]}
TRACE = [{'id':f'demo-{i}', 'action_id':f'compare-{i}', 'before':{'count':i-1}, 'after':{'count':i}, 'facts':{'count':i}, 'done':i==3} for i in range(1,4)]
CATALOG = [{'id':'swap','label':'交换','rule':'正确选择增加count，三次完成','facts':['count']},
           {'id':'keep','label':'保持','rule':'错误操作','facts':['count']}]
NARRATION = {'overview':'按实际动作学习',
             'demo_steps':[{'id':r['id'],'title':r['action_id'],'before':f"即将执行第{i+1}次比较",'after':f"已执行第{i+1}次比较"} for i,r in enumerate(TRACE)],
             'tasks':[{'id':f'task-{i+1}','prompt':'完成连续比较','hints':['观察当前值']} for i in range(2)],
             'action_feedback':[{'action_id':'swap','pending':'已完成 {{facts.count}} 次，原来是 {{before.count}} 次。','passed':'完成 {{after.count}} 次。','fail':''},
                                {'action_id':'keep','pending':'','passed':'','fail':'当前为 {{before.count}} 次，请重新判断。'}],
             'exploration_prompts':['观察计数变化']}
ACTION_RAW = RAW.replace('EduStage.register({', 'EduStage.register({actions:'+__import__('json').dumps(CATALOG,ensure_ascii=False)+',')\
    .replace('next(index){state.count=index+1;draw()}', "next(index){state.count++;draw();return{action_id:'compare-'+state.count,done:state.count===3,facts:{count:state.count}}}")\
    .replace("return{verdict:'pass'}", "return{action_id:'swap',verdict:state.count===3?'pass':'pending',facts:{count:state.count}}")\
    .replace("return{verdict:'fail'}", "return{action_id:'keep',verdict:'fail',facts:{count:state.count}}")
