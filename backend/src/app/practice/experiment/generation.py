"""Generic experiment design Skill -> unchanged MAIC native generators -> checks."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import time
from .contracts import PROTOCOL, digest

SKILL = Path(__file__).resolve().parents[1] / 'skills/design-experiment'

def integration(spec):
    return '''\n【Edu_AI 通用三阶段实验适配，优先于上文的页面控制建议】
只生成中央实验展示与必要的画布/对象交互。宿主提供标题、三个阶段、下一步、任务提示、参数表单和按钮。
不要在页面重复阶段导航、参数面板、聊天框或自动启动模拟；不能绕过宿主直接改状态。
保留 MAIC-UI 的视觉质量和科学模型。宿主内置 Tailwind 4 和 KaTeX，不下载资源、不发起网络请求。
正文16px、图表标签至少13px、展示高度至少360px。360px宽度仍可读。canvas位图按CSS尺寸乘devicePixelRatio；ResizeObserver重绘只读最近状态，不能累积缩放。
''' + (SKILL / 'references/runtime.md').read_text() + '\n必须实现以下全部动作和状态字段，不能改动规格。演示/验收规则由平台执行，禁止伪造验收结果。\n' + json.dumps(spec, ensure_ascii=False)

async def generate(command, context):
    from .. import service
    from ..native import generate_native, postprocess_native, PRESENTATION, REVISION
    from ..native_runtime import wrap_native_html
    def progress(value, stage, message):
        if context.is_cancel_requested():
            from app.services.durable_task_handlers import DurableTaskExecutionError
            raise DurableTaskExecutionError('GENERATION_CANCELLED', '实验生成已取消')
        context.progress(value, stage, message)
    progress(8, 'experiment_design', '正在设计演示、关键练习和自由探索')
    from .design import design
    spec, adjustments = await design(command['topic'], context, service.complete, service.PracticeStore())
    revision = digest(spec)
    plan = {'subject': spec['subject'], 'concept_name': spec['title'], 'concept_overview': spec['overview'], 'mastery_points': '\n'.join(spec['objectives']), 'design_idea': spec['teaching_context']['background'], 'steps': [{'title': s['title'], 'instruction': s['before'], 'question': s['after']} for s in spec['demo_steps']], 'experiment': spec}
    generated = await generate_native(plan, context, service.complete)
    raw = generated['html']
    for attempt in range(2):
        progress(82 + 8 * attempt, 'experiment_validation', '正在执行演示、正确与错误操作并检查页面')
        try:
            html = wrap_native_html(postprocess_native(raw), experiment={'spec': spec, 'revision': revision})
            check = await asyncio.to_thread(service.validate_html, html, native=True, experiment=spec)
        except ValueError as exc: check = {'ok': False, 'issues': [str(exc)]}
        if check['ok']: break
        if attempt: raise ValueError('实验未通过运行验收：' + '；'.join(check['issues'])[:400])
        raw = await service.complete(context.owner_user_id, '修复实验，返回完整HTML。' + integration(spec) + '\n科学模型：' + json.dumps(generated['science'], ensure_ascii=False) + '\n原代码：' + raw + '\n运行问题：' + json.dumps(check, ensure_ascii=False), tokens=24000)
    progress(98, 'experiment_save', '实验已通过运行检查，正在保存')
    from .bundle import bundle
    artifact = {'id': context.task_id, 'topic': command['topic'], 'plan': plan, 'science': generated['science'], 'html': html, 'raw_html': raw, 'presentation': PRESENTATION, 'validation': check, 'design_adjustments': adjustments, 'created_at': time.time(), 'experiment': {'protocol': PROTOCOL, 'spec': spec, 'revision': revision, 'runtime': bundle().stem, 'teaching': {'status': 'reserved', 'context_version': 'edu-experiment-context/1'}}, 'generation_info': generated['generation_info'], 'native_calls': generated['native_calls'], 'source': {'project': 'THU-MAIC/MAIC-UI', 'revision': REVISION, 'integration': 'native-heavy-generator', 'modules': ['ScientificEngine', 'HeavyGenerator', 'PostProcessor']}}
    store = service.PracticeStore(); store.put(context.owner_user_id, context.task_id, artifact)
    if store.get(context.owner_user_id, context.task_id).get('experiment', {}).get('revision') != revision: raise RuntimeError('实验保存校验失败')
    return service.result_ref(context.task_id)
