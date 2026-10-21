"""Science -> complete HTML -> action plan -> stage HTML -> executed trace -> narration."""
import asyncio
import json
import time
from pathlib import Path
from pydantic import ValidationError
from app.integrations.llm_client import parse_llm_json
from ..experiment.contracts import digest
from .contracts import PROTOCOL
from .narration import ACTION_PROTOCOL, TWO_STAGE_PIPELINE, DemonstrationPlan, ExplorationNarration, action_spec, bind_narration

SKILL = Path(__file__).resolve().parents[1] / 'skills/design-experiment'

async def generate(command, context):
    from .. import service
    from ..native import load_native, PlatformProvider, REVISION
    from ..native_runtime import wrap_native_html
    store = service.PracticeStore(); owner = context.owner_user_id; key = context.task_id + ':pages-draft'
    draft = store.get(owner, key) or {'protocol': PROTOCOL, 'stages': {}}
    if draft.get('pipeline') != TWO_STAGE_PIPELINE:
        # Reuse only neutral source material from older drafts, never prose-first pages.
        draft = {'protocol': PROTOCOL, 'pipeline': TWO_STAGE_PIPELINE, 'stages': {
            k: v for k, v in draft['stages'].items() if k in ('science', 'explore')}}
    stages = draft['stages']
    def progress(value, stage, message):
        if context.is_cancel_requested():
            from app.services.durable_task_handlers import DurableTaskExecutionError
            raise DurableTaskExecutionError('GENERATION_CANCELLED', '实验生成已取消')
        context.progress(value, stage, message)
    def save(name, result):
        stages[name] = result; draft['updated_at'] = time.time(); store.put(owner, key, draft)
    native = load_native(); provider = PlatformProvider(service.complete, owner, context, page_instructions='')
    topic = command['topic']
    concept = {'concept_name': topic, 'subject': '互动实验', 'concept_overview': topic, 'mastery_points': topic,
               'design_idea': '根据用户需求生成完整可交互实验，默认入门难度，提供必要参数、单步或运行、重置。用户需求：' + topic}
    progress(8, 'practice_science', '正在建立实验的科学模型')
    if 'science' not in stages:
        science = await native.processor.ScientificEngine(provider).run(concept)
        if science.raw_analysis == 'Error during modeling' or not science.raw_analysis:
            raise ValueError('科学建模未完成，请重试')
        save('science', {'core_formulas': science.core_formulas, 'mechanism': science.mechanism, 'constraints': science.constraints, 'forbidden_errors': science.forbidden_errors, 'raw_analysis': science.raw_analysis})
    science_data = stages['science']; science = native.processor.ScientificModel.from_dict(science_data)
    science.raw_analysis = science_data['raw_analysis']
    runtime = (SKILL / 'references/pages-runtime.md').read_text() + '\n' + (SKILL / 'references/state-evidence.md').read_text()
    provider.page_system = '你是实验页面实现者。以下是必须遵守的阶段接口与交互规则；基础HTML仅作为算法和绘图参考，不能覆盖这些规则。\n' + runtime
    instructions = '\n【Edu_AI 页面适配，优先遵守】\n' + runtime + '\n完整科学模型：' + json.dumps(science_data, ensure_ascii=False)
    async def page(name, value, requirements, spec):
        progress(value, 'experiment_' + name, {'explore': '正在生成完整实验', 'demonstrate': '正在改造原理演示页面', 'guided': '正在改造动手练习页面'}[name])
        if name in stages: return stages[name]['html']
        provider.phase = name; provider.page_instructions = instructions + '\n本次阶段：' + name + '\n' + requirements
        local = concept
        for attempt in range(2):
            progress(value, 'experiment_' + name, '正在生成实验页面' if not attempt else '正在修复该页面的运行问题')
            raw = await native.processor.VisualEngine(provider).run(local, science, {'grade_level': 10})
            try:
                html = wrap_native_html(native.processor.PostProcessor.run(raw), stage_page={'phase': name, 'spec': spec, 'revision': digest(spec)})
                check = await asyncio.to_thread(service.validate_html, html, stage_page={'phase': name, 'spec': spec})
            except ValueError as exc: check = {'ok': False, 'issues': [str(exc)]}
            save(name + '-attempt-' + str(attempt+1), {'html': raw, 'check': check})
            if check['ok']:
                save(name, {'html': raw, 'check': check}); return raw
            if attempt: raise ValueError('实验页面基本运行检查未通过：' + '；'.join(check['issues'])[:400])
            provider.page_instructions = instructions + '\n本次阶段：' + name + '\n' + requirements + '\n只修复运行问题，沿用原算法和教学方案。原页面：\n' + raw + '\n问题：' + json.dumps(check, ensure_ascii=False)
        raise AssertionError('unreachable')
    placeholder = {'protocol': PROTOCOL, 'title': topic, 'overview': topic, 'demo_steps': [], 'tasks': [], 'exploration_prompts': [], 'actions': [], 'state_fields': [], 'teaching_context': {'background': topic, 'misconceptions': []}}
    base_html = await page('explore', 25, '生成完整自由探索实验。遵循科学模型，保留完整交互。实现探索页的 EduStage 接口，所有用户操作上报。', placeholder)
    progress(48, 'experiment_split', '正在设计原理演示动作')
    if 'action-plan' not in stages:
        design_system = (SKILL / 'SKILL.md').read_text()
        prompt = '用户需求：' + topic + '\n科学模型：' + json.dumps(science_data, ensure_ascii=False) + '\n已有完整实验 HTML（保留算法和绘图，只设计原理演示动作，不设计动手任务）：\n' + base_html + '\n只输出以下 JSON 结构：' + json.dumps(DemonstrationPlan.model_json_schema(), ensure_ascii=False)
        for attempt in range(2):
            progress(48, 'experiment_split', '正在拆分动作，不生成讲解')
            raw = await service.complete(owner, prompt, system=design_system, tokens=6500)
            try:
                plan = DemonstrationPlan.model_validate(parse_llm_json(raw)).model_dump()
                save('action-plan', plan); break
            except (ValueError, TypeError) as exc:
                errors = exc.errors(include_input=False, include_context=False, include_url=False) if isinstance(exc, ValidationError) else str(exc)
                save('split-attempt-' + str(attempt+1), {'raw': raw, 'errors': errors})
                if attempt: raise ValueError('教学拆分格式未完成，请重试') from exc
                prompt += '\n上次输出：' + raw + '\n修复这些字段并返回完整教学拆分：' + json.dumps(errors, ensure_ascii=False)
    spec = {**action_spec(stages['action-plan'], science_data), 'phases': ['demonstrate', 'explore']}
    shared = '\n科学模型：' + json.dumps(science_data, ensure_ascii=False) + '\n完整基础实验（必须沿用计算和绘图，只改本阶段操作）：\n' + base_html
    demo_html = await page('demonstrate', 64, '生成原理演示版。移除所有自由控件，宿主提供下一步/回看/重播。按下列 demo_initial 和动作方案实现 initialize/next。方案描述动作与边界，不是固定执行次数。每次next只执行一个实际操作，返回实际 action_id、done 和 facts；直到整个算法或实验目标真实结束。不要生成教学讲解，讲解将在实际执行后另行生成。\n' + json.dumps({k: spec[k] for k in ['demo_initial', 'demo_steps']}, ensure_ascii=False) + shared, spec)
    trace = stages['demonstrate']['check'].get('trace', [])
    if not trace:
        raise ValueError('演示动作记录缺失，请重新生成演示页面')
    progress(90, 'experiment_narration', '正在根据实际动作与状态生成讲解')
    if 'narration' not in stages:
        prompt = ('用户需求：' + topic + '\n科学模型：' + json.dumps(science_data, ensure_ascii=False)
                  + '\n演示动作方案与步骤ID：' + json.dumps(spec, ensure_ascii=False)
                  + '\n演示实际执行记录（id、action_id、before、after、facts、done）：' + json.dumps(trace, ensure_ascii=False)
                  + '\n自由探索HTML（只针对已实现控件给探索建议）：\n' + base_html
                  + '\n只输出讲解JSON：' + json.dumps(ExplorationNarration.model_json_schema(), ensure_ascii=False)
                  + '\n演示文字依据实际数值，不使用模板。提供1至3条可选探索建议，每条一句话，说明可改的真实控件与观察重点；没有任务、评分或通关要求。')
        for attempt in range(2):
            raw = await service.complete(owner, prompt, system=(SKILL / 'references/narration.md').read_text(), tokens=10000)
            try:
                narrative = ExplorationNarration.model_validate(parse_llm_json(raw)).model_dump()
                save('narration', narrative); break
            except (ValueError, TypeError) as exc:
                errors = exc.errors(include_input=False, include_context=False, include_url=False) if isinstance(exc, ValidationError) else str(exc)
                save('narration-attempt-' + str(attempt+1), {'raw': raw, 'errors': errors})
                if attempt: raise ValueError('动作讲解格式未完成，请重试') from exc
                prompt += '\n上次输出：' + raw + '\n仅修复讲解JSON格式：' + json.dumps(errors, ensure_ascii=False)
    spec = bind_narration(spec, trace, [], stages['narration'])
    progress(96, 'experiment_save', '正在组合原理演示与自由探索并保存实验')
    raw_pages = {'explore': base_html, 'demonstrate': demo_html}
    revision = digest({'spec': spec, 'pages': raw_pages})
    pages = {phase: wrap_native_html(native.processor.PostProcessor.run(raw), stage_page={'phase': phase, 'spec': spec, 'revision': revision}) for phase,raw in raw_pages.items()}
    # Validate the exact assembled package, not only pages with draft settings.
    # This is a local integration check, not another model review.
    final_checks = {}
    for phase, html in pages.items():
        check = await asyncio.to_thread(service.validate_html, html, stage_page={'phase': phase, 'spec': spec})
        final_checks[phase] = check
        if not check['ok']:
            save('assembled-checks', final_checks)
            raise ValueError('实验拼装后运行检查未通过：' + '；'.join(check['issues'])[:400])
    save('assembled-checks', final_checks)
    artifact = {'id': context.task_id, 'topic': topic, 'created_at': time.time(), 'html': pages['demonstrate'], 'raw_html': base_html,
                'plan': {'concept_name': spec['title'], 'concept_overview': spec['overview'], 'steps': [{'title':s['title'], 'instruction':s['before'], 'question':s['after']} for s in spec['demo_steps']]},
                'action_evidence': {'protocol': ACTION_PROTOCOL, 'demo_trace': trace, 'phases': ['demonstrate', 'explore']},
                'science': science_data, 'presentation': 'maic-ui-staged-pages-v2',
                'experiment': {'protocol': PROTOCOL, 'revision': revision, 'spec': spec, 'pages': pages, 'teaching': {'status': 'reserved', 'context_version': 'edu-experiment-context/1'}},
                'validation': {'ok': True, 'scope': 'assembled-page-runtime', 'pages': final_checks, 'scientific_certification': False},
                'native_calls': provider.calls, 'source': {'project': 'THU-MAIC/MAIC-UI', 'revision': REVISION, 'modules': ['ScientificEngine', 'VisualEngine', 'PostProcessor']}}
    store.put(owner, context.task_id, artifact)
    if store.get(owner, context.task_id).get('experiment', {}).get('revision') != revision: raise RuntimeError('实验保存校验失败')
    return service.result_ref(context.task_id)
