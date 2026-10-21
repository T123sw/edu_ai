from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import signal
from pathlib import Path
import shutil
import subprocess
import time

import httpx
from pydantic import BaseModel, Field
from typing import Literal
from app.chat.bounded_completion import BoundedModelAdapter
from app.integrations.llm_client import parse_llm_json
from app.self_learning.store import LearningStore
from app.services.runtime_config_resolver import runtime_config_resolver
from app.services.durable_task_handlers import DurableTaskExecutionError
from .native import REVISION

ROOT = Path(__file__).resolve().parents[4]

class PracticeStore(LearningStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = self.root.parent / 'practice'
    def _namespace(self, owner):
        return 'practice:' + hashlib.sha256(owner.encode()).hexdigest()

class Step(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=1200)
    question: str = Field(min_length=1, max_length=400)

class Plan(BaseModel):
    guided_kind: Literal["quicksort", "friction", "generic"] = "generic"
    subject: str = Field(min_length=1, max_length=100)
    concept_name: str = Field(min_length=1, max_length=150)
    concept_overview: str = Field(min_length=1, max_length=2000)
    mastery_points: str = Field(min_length=1, max_length=2000)
    design_idea: str = Field(min_length=1, max_length=4000)
    steps: list[Step] = Field(min_length=1)


def upstream():
    from .native import load_native
    from .native_runtime import assets
    native = load_native()
    assets()
    return native

async def complete(owner, prompt, *, system='你是交互式教学实验设计师。', tokens=16000):
    config = runtime_config_resolver.resolve('llm', owner_user_id=owner)
    gateway = BoundedModelAdapter.from_config(config).gateway
    previous_status = None
    for candidate in gateway.candidates:
        if candidate.get('only_after_status') and candidate['only_after_status'] != previous_status:
            continue
        model = candidate['model_name']
        extra = gateway._thinking_params(model)
        if str(model).lower().startswith('deepseek-v4'):
            extra = {**extra, 'thinking': {'type': 'disabled'}}
        payload = dict(model=model, messages=[{'role':'system','content':system},{'role':'user','content':prompt}], max_tokens=tokens, temperature=0.3, stream=False, **extra)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(360, connect=15), trust_env=candidate.get('trust_env', True)) as client:
                response = await client.post(candidate['api_base'].rstrip('/')+'/chat/completions', headers=gateway._build_headers(candidate.get('api_key')), json=payload)
                response.raise_for_status()
                data = response.json()
                choice = (data.get('choices') or [{}])[0]
                logging.getLogger(__name__).info('Practice completion model=%s finish=%s tokens=%s', model, choice.get('finish_reason'), data.get('usage', {}).get('completion_tokens'))
                if choice.get('finish_reason') == 'length':
                    raise ValueError('模型输出被长度限制截断，请缩小实验主题后重新生成')
                return BoundedModelAdapter.parse(data)['content']
        except httpx.HTTPStatusError as exc:
            previous_status = exc.response.status_code
            logging.getLogger(__name__).warning('Practice provider status: %s', previous_status)
            if previous_status != 402:
                raise RuntimeError('模型服务暂不可用，请稍后重试') from None
    raise RuntimeError('模型服务暂不可用，请检查模型配置')


def validate_html(html, *, native=False, guidance=None, experiment=None, stage_page=None):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('实验浏览器检查需要 Node.js')
    process = subprocess.Popen([node, str(ROOT/'frontend/scripts/validate-practice.mjs')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT/'frontend', start_new_session=True)
    try:
        output, _ = process.communicate(json.dumps({'html':html, 'native':native, 'guidance':guidance, 'experiment':experiment, 'stage_page':stage_page}), timeout=120 if experiment or stage_page else 90 if guidance else 55)
        if process.returncode:
            raise RuntimeError('实验浏览器检查未完成，请检查 Playwright/Chromium 安装')
        return json.loads(output)
    finally:
        # Kill the whole browser process group on timeout, including Chromium children.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

async def generate(command, context):
    store = PracticeStore()
    cached = store.get(context.owner_user_id, context.task_id)
    if cached.get('html'):
        return result_ref(context.task_id)
    upstream()
    if command.get('protocol') == 'edu-experiment/2':
        from .pages.generation import generate as generate_pages
        return await generate_pages(command, context)
    if command.get('protocol') == 'edu-experiment/1':
        from .experiment.generation import generate as generate_experiment
        return await generate_experiment(command, context)
    from .native import generate_native, postprocess_native, INTEGRATION, PRESENTATION
    from .native_runtime import wrap_native_html
    def progress(value, stage, message):
        if context.is_cancel_requested():
            raise DurableTaskExecutionError('GENERATION_CANCELLED', '实验生成已取消')
        context.progress(value, stage, message)
    progress(10, 'practice_plan', '正在把主题设计成可动手的实验')
    plan = Plan.model_validate(parse_llm_json(await complete(context.owner_user_id, '根据用户主题设计一个浏览器内可运行的探索实验，默认入门难度。guided_kind仅在主题是快速排序时为quicksort，在水平面恒定滑动摩擦的小车运动时为friction，其他主题必须为generic。按学习目标划分由学生亲自操作的步骤，每步描述改什么、观察什么、思考什么。返回严格JSON，结构为：'+json.dumps(Plan.model_json_schema(),ensure_ascii=False)+'\n用户主题：'+command['topic'], tokens=3500)))
    data = plan.model_dump()
    from .guidance.contracts import make_manifest
    guidance = make_manifest(plan.guided_kind)
    if guidance:
        data['steps'] = [{key: step[key] for key in ('title','instruction','question')} for step in guidance['steps']]
        data['guidance'] = guidance
    generated = await generate_native(data, context, complete)
    raw = generated['html']
    for attempt in range(2):
        progress(82+attempt*8, 'practice_check', '正在检查高清显示、重绘、参数与运行按钮' if not attempt else '正在修复并重新检查原生实验')
        try:
            html = wrap_native_html(postprocess_native(raw), guidance=guidance)
            check = await asyncio.to_thread(validate_html, html, native=True, guidance=guidance)
        except ValueError as exc:
            check = {'ok':False,'issues':[str(exc)]}
        if check['ok']:
            break
        if attempt:
            raise ValueError('实验运行检查未通过：'+'；'.join(check['issues'])[:400])
        from .guidance.generation import integration
        guided_contract = integration(guidance) if guidance else ''
        raw = await complete(context.owner_user_id, '修复以下 MAIC-UI 原生实验，保留全部教学内容、布局与交互。'+INTEGRATION+guided_contract+'\n科学约束与步骤：'+json.dumps({'science':generated['science'],'steps':data['steps']},ensure_ascii=False)+'\n上次代码：\n'+raw+'\n浏览器检查问题：'+json.dumps(check,ensure_ascii=False)+'\n请修复并输出完整HTML。', tokens=24000)
    progress(98, 'practice_save', '原生实验已通过运行与显示检查，正在保存')
    store.put(context.owner_user_id, context.task_id, {
        'id':context.task_id,'topic':command['topic'],'plan':data,'science':generated['science'],
        'html':html,'raw_html':raw,'presentation':PRESENTATION,'validation':check,'created_at':time.time(),
        'guidance_version':2 if guidance else None,'guidance':guidance,
        'generation_info':generated['generation_info'],'native_calls':generated['native_calls'],
        'source':{'project':'THU-MAIC/MAIC-UI','revision':REVISION,'integration':'native-heavy-generator',
                  'modules':['ScientificEngine','HeavyGenerator','PostProcessor']},
    })
    if not store.get(context.owner_user_id,context.task_id).get('html'):
        raise RuntimeError('实验保存校验失败')
    return result_ref(context.task_id)

def result_ref(identifier):
    return {'saved':True,'result_ref':{'resource_type':'practice','practice_id':identifier},'completion_message':'互动实验已就绪，可以进入操作'}

class PracticeTaskHandler:
    def __call__(self, command, context):
        try:
            return asyncio.run(generate(command,context))
        except asyncio.CancelledError as exc:
            raise DurableTaskExecutionError('GENERATION_CANCELLED', '实验生成已取消') from exc
        except DurableTaskExecutionError:
            raise
        except Exception as exc:
            logging.getLogger(__name__).exception('Practice generation failed')
            message = str(exc)[:450] if isinstance(exc, ValueError) else '实验生成未完成，请稍后重新生成；详细原因已记入服务日志'
            raise DurableTaskExecutionError('PRACTICE_GENERATION_FAILED', message) from exc
