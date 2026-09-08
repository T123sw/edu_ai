"""Real Harness/Skill/search/organization/outline acceptance, isolated file state."""
from pathlib import Path
import argparse
import json
import os
import sys
import time
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'backend/src'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    from core.config import Config
    import dotenv
    dotenv.load_dotenv = lambda *a, **k: False
    for key in ('USER','JOB','TASK','MATERIAL','COURSE','COURSE_MEMBERSHIP','KNOWLEDGE','APP_STATE','CONVERSATION','LEARNING'):
        os.environ[key+'_PERSISTENCE_MODE'] = 'json'
    os.environ['DATABASE_URL'] = ''
    for name in ('STORAGE_ROOT','COURSE_STORAGE_ROOT','RUNTIME_CONFIG_ROOT'):
        setattr(Config, name, output / name.lower())
        os.environ[name] = str(getattr(Config, name))
    os.chdir(output)
    from app.chat.harness.runtime import HarnessRuntime
    from app.chat.harness.store import HarnessStore
    from app.chat.harness.tools import ReportTools
    from app.chat.tools.agent_tools import web_search_tool
    from app.chat.harness.content_gateway import build_content_gateway
    from app.chat.domain.contracts import ChatRequestV2
    from app.chat.domain.conversation_snapshot import ConversationSnapshot
    def forbidden(*a, **k):
        raise AssertionError('Outline acceptance must not submit or access report jobs')
    def factory(**kwargs):
        return ReportTools(**kwargs, gateway=build_content_gateway(), web=web_search_tool,
            submit=forbidden, get_job=forbidden, read_artifact=forbidden, cancel_job=forbidden,
            validate_scope=lambda request: None)
    request = ChatRequestV2(owner='outline-acceptance', course_id='synthetic', conversation_id='binary-search',
        request_id='outline-1', capability={'allow_web': True, 'allow_rag': False},
        question='请为掌握 Python 循环和数组的大学初学者制作一份知识点报告大纲：二分查找的循环不变量与边界处理。只交付大纲，不生成正文。请联网查找大学课程或官方资料作为依据。可用来源 https://docs.python.org/3/library/bisect.html 和 https://www.cs.cornell.edu/courses/cs2112/2019fa/lectures/loopinv/ ，搜索无法命中时通过 reference_urls 读取这些页面，先组织内容再生成5章大纲。聚焦有序数组、闭区间与半开区间、终止与更新规则、重复值的左边界，提供具体输入示例、常见错误和可检验学习目标；不扩展到树或整门算法课。注意：Cornell 讲义假设目标存在，不能把它的不变量直接套到目标可不存在的查找。匹配值查找和左侧插入点须分别约定返回值；不变量在退出时仍成立，插入点可等于n须先检查范围再访问。人工审阅约束：闭区间用于查任一匹配索引，l=0,r=n-1,while l<=r，相等立即返回m，小于目标l=m+1，大于目标r=m-1，退出返回-1；不变量是0<=l<=r+1<=n，a[:l]均小于x，a[r+1:]均大于x。半开区间用于左插入点，l=0,r=n,while l<r，a[m]<x则l=m+1否则r=m；不变量0<=l<=r<=n，a[:l]均小于x，a[r:]均大于等于x，退出返回l；确认存在须l<n且a[l]==x。示例应分别覆盖空数组、单元素、重复值以及目标大于所有元素。不要将这两种不同返回契约说成仅切换区间记号。')
    runtime = HarnessRuntime(store=HarnessStore(output/'sessions'), tool_factory=factory,
        model=Config.DSH_MODEL, api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL, timeout=300)
    start=time.monotonic()
    events=[]
    for event in runtime.run_stream(request=request, snapshot=ConversationSnapshot()):
        events.append(event)
        if event['type'] in ('tool_call','tool_result'):
            payload=event['payload']
            print(json.dumps({'event':event['type'],'tool':payload.get('tool'),'ok':payload.get('ok')},ensure_ascii=False),flush=True)
    (output/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
    result=next(e['payload'] for e in reversed(events) if e['type']=='result')
    assert result.get('harness_outline'), result.get('message')
    successful={e['payload']['tool'] for e in events if e['type']=='tool_result' and e['payload'].get('ok')}
    assert {'web_search','organize_report_content','draft_report_outline'} <= successful, successful
    assert not any(e['type']=='tool_call' and e['payload']['tool']=='submit_report' for e in events)
    states=list((output/'sessions').glob('*/state.json'))
    state=json.loads(states[0].read_text())
    outline=state['outlines'][state['active_outline']]
    assert outline['organization_id'] and len(outline['chapters'])==5
    assert not state['jobs']
    native=[]
    for path in (output/'sessions').glob('*/events.jsonl'):
        for line in path.read_text().splitlines():
            event=json.loads(line).get('harness_event', {})
            if event.get('type')=='tool/call':
                native.append(event.get('data',{}).get('name'))
    assert 'skill' in native, native
    (output/'outline.md').write_text(outline['markdown'])
    (output/'verification.json').write_text(json.dumps({'passed':True,'seconds':round(time.monotonic()-start,2),
        'live_sdk':True,'live_web_search':True,'native_tools':native,'tools':sorted(successful),'outline':outline,
        'evidence':state['evidence'],'organization':state['organizations'][outline['organization_id']],
        'semantic_review':'pending'},ensure_ascii=False,indent=2))
    print('PASS '+str(output),flush=True)
if __name__=='__main__':
    main()
