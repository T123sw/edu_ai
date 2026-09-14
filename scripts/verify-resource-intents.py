"""Isolated native service and real model intent regression; never mutates user artifacts."""
from pathlib import Path
import sys,os,json,time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend/src'))
from core.config import Config
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
for key in ('JOB','MATERIAL','COURSE','KNOWLEDGE','TASK','USER','COURSE_MEMBERSHIP','CONVERSATION','APP_STATE'):
 os.environ[key+'_PERSISTENCE_MODE']='json'
os.environ['DATABASE_URL']='';os.environ['PERSISTENCE_PROFILE']='compatibility'
import argparse
parser=argparse.ArgumentParser(description='Live model decisions: new resource, edit, and read-only with conflicting history')
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
root=args.output.resolve();root.mkdir(parents=True, exist_ok=True)
os.chdir(root)
from core.course_storage import CourseStorageManager
from app.artifact_revision.service import ArtifactRevisionService
from app.chat.agents.report_generation import get_fallback_llm
manager=CourseStorageManager(str(root/'courses'))
original='# 数组\n\n## 内存布局\n\n数组按下标访问。\n\n## 课堂示例\n\n原始案例。'
for kind in ('report','lesson_plan'):
 manager.save_generated_material('course',kind,kind,{'title':'数组'+('报告' if kind=='report' else '教案'),'content':original},owner_user_id='teacher',visibility='private')
cases=[
 ('same_type_new_report','report',None,'帮我生成一份数组实现的报告','new_resource','report'),
 ('report_after_lesson_edit','report','把报告改成教案','现在请生成一份报告，主题是数组的实现','new_resource','report'),
 ('lesson_after_report_edit','report','给旧报告补一个例子','帮我生成数组的实现的教案','new_resource','lesson_plan'),
 ('report_from_lesson','lesson_plan',None,'根据这份教案生成一份报告','new_resource','report'),
 ('edit_example','report',None,'给这份报告的课堂示例增加一个具体例子，其他部分不变','preview',None),
 ('regenerate_section','report',None,'重新生成这份报告中的课堂示例，保留其余正文','preview',None),
 ('read_only','report','把报告改成教案','先别修改，解释一下这份报告在讲什么','answered',None),
]
def run(case):
 name,kind,old,question,status,target=case
 ref={'artifact_id':kind,'artifact_type':kind,'version_id':'v1','source_course_id':'course'}
 pending=None
 if old:
  pending={'owner_user_id':'teacher','conversation_id':name,'operation_id':name,'course_id':'course','scope_id':None,'reference':ref,'question':old,'draft':{'draft_id':name,'revision':1,'content':original,'focus':'课堂示例','reason':'旧修改','benefit':'旧目标'}}
 start=time.monotonic()
 try:
  result=ArtifactRevisionService(manager,get_fallback_llm()).run(owner_user_id='teacher',conversation_id=name,course_id='course',question=question,operation_id=name,artifact_reference=ref,pending=pending)
  intent=(result.get('source_context') or {}).get('creation_intent')
  passed=result['status']==status and (not target or intent['resource_type']==target)
  assert manager.get_generated_material('course',kind,kind,owner_user_id='teacher')['content']==original
  return {'case':name,'question':question,'previous_edit_request':old,'status':result['status'],'intent':intent,'passed':passed,'seconds':round(time.monotonic()-start,1),'message':result.get('message','')[:200]}
 except Exception as e:return {'case':name,'passed':False,'error':str(e)[:300]}
results=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(run,cases):
  results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
(root/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
assert all(r['passed'] for r in results),results
