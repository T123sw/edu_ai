"""Submit one idempotent, scoped revision through the established preparation API."""
import json
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from app.chat.tasks.task_store import get_task_store
from app.course_preparation.pipeline import build_pipeline
from app.course_preparation.schemas import PreparationRequest

request_data = dict(
    request_id=UUID('f465dd74-f753-4ff7-aee1-409cd7fe5af9'), operation='revise_resource',
    goal='修复 Transformer 第二节点现有习题的确定性数值错误，保留全部原题 ID、题型、学习目标及其他正确内容，只修改受影响的答案与解析。',
    target={'course_id':'learn-65488c25779346448e1dcbe0b809d73e','base_manifest_version':21,
            'node_id':'n2-self-attention','resource_id':'resource_471ae3cd827344574d74384701f842c1','base_resource_version':1},
    overrides={'include_classroom':False, 'required_resource_types':['quiz']},
    requested_changes=(
        'q6-hand-calc-weights 与 q7-hand-calc-output 中，未缩放 softmax([1,0,1]) 的正确值是 [0.4223187982515182,0.15536240349696362,0.4223187982515182]，保留三位为 [0.422,0.155,0.422]。删除错误的 [0.422,0.207,0.371]。',
        'q7 未缩放权重对 V=[[1,0],[0,1],[1,1]] 加权的第一行应为 [0.8446375965030364,0.5776812017484818]，保留两位是 [0.84,0.58]；删除错误的 [0.79,0.58]。',
        '缩放后的第三行真实权重为 [0.2482550782577231,0.2482550782577231,0.5034898434845538]，保留三位应是 [0.248,0.248,0.503]，不是 0.504。完整精度的和为1，三位显示值之和为0.999；解释舍入误差，不能为了凑1调整某个概率。',
        'q6/q7 相关算式和中间结果统一从完整精度计算后舍入，避免先舍入至0.5035再二次舍入至0.504。缩放输出第一行 [0.8022241853595718,0.5988879073202141]，第三行 [0.7517449217422769,0.7517449217422769]。保留已正确的两位最终结果。',
        '这是一份已有习题的局部纠错，不新增视频或报告，不删除和重排题目；独立复算所有修改，保留原题与原学习目标的映射。'))
request_data['goal'] += '\n' + '\n'.join(request_data.pop('requested_changes'))
request = PreparationRequest(**request_data)
app = build_pipeline(get_task_store())
receipt = app.service.submit('teacher', request)
output = ROOT/'docs/acceptance/2026-10-19-adaptive-video-concurrency/quiz-revision.json'
output.write_text(json.dumps({'request':request.model_dump(mode='json'),'receipt':receipt},ensure_ascii=False,indent=2,default=str))
print(json.dumps({'preparation_id':receipt['preparation_id'],'status':receipt['status']},ensure_ascii=False))
