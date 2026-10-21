"""Keep the correction task narrow when legacy path review overreaches."""
import json,sys
from pathlib import Path
from uuid import UUID
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from app.chat.tasks.task_store import get_task_store
from app.course_preparation.pipeline import build_pipeline
from app.course_preparation.schemas import PreparationRequest
root=ROOT/'docs/acceptance/2026-10-19-adaptive-video-concurrency'
app=build_pipeline(get_task_store())
previous=json.loads((root/'quiz-exact-revision.json').read_text())['receipt']['preparation_id']
state=app.service.get('teacher',previous)
if state['status']=='succeeded':
    print('Exact revision already completed');sys.exit()
if state['status'] not in ('canceled','failed'):
    stopped=app.service.cancel('teacher',previous,expected_attempt_no=1)
    (root/'superseded-revision.json').write_text(json.dumps(stopped,ensure_ascii=False,indent=2,default=str))
request=PreparationRequest(request_id=UUID('44d7b83f-ccfc-4193-89b6-3eb9b12d3c44'),operation='revise_resource',
 goal='修正这套现有习题第6、7题解析中遗留的小数误差。正确的缩放第一行权重是 [0.4011120926797859,0.1977758146404282,0.4011120926797859]，请替换解析中错误的 0.40110905 和 0.19778190，并同步所有引用。第6题指数示例请使用符号形式 exp(1/√2)、exp(√2)，删除不必要的指数中间近似数及分母小数，直接列出经完整精度计算的权重，避免又引入近似误差。第7题用完整精度权重计算，第一行输出约 [0.8022241853595718,0.5988879073202141]，第三行约 [0.7517449217422769,0.7517449217422769]。保留现在已经正确的三位权重、两位输出及未缩放对照。保留原9题编号、题干、题型和学习目标，其余正确内容无需改写。',
 target={'course_id':'learn-65488c25779346448e1dcbe0b809d73e','base_manifest_version':22,'node_id':'n2-self-attention','resource_id':'resource_471ae3cd827344574d74384701f842c1','base_resource_version':2},
 overrides={'include_classroom':False,'required_resource_types':['quiz']})
receipt=app.service.submit('teacher',request)
(root/'quiz-minimal-revision.json').write_text(json.dumps({'request':request.model_dump(mode='json'),'receipt':receipt},ensure_ascii=False,indent=2,default=str))
print(json.dumps({'previous':previous,'preparation_id':receipt['preparation_id'],'status':receipt['status']}))
