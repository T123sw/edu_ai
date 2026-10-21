"""Design boundary: explicit schema, narrow normalization and owned diagnostics."""
from copy import deepcopy
import json
from pathlib import Path
import time
from pydantic import ValidationError
from app.integrations.llm_client import parse_llm_json
from .contracts import ExperimentSpec

SKILL = Path(__file__).resolve().parents[1] / 'skills/design-experiment'


def normalize_design(payload):
    """submission is authoritative; explicit-submit runtime never uses submit_action.

    Remove only that inactive string field. Keep all operations, checks and task
    order unchanged; missing modes or invalid automatic actions still fail.
    """
    result = deepcopy(payload); changes = []
    if isinstance(result, dict) and isinstance(result.get('tasks'), list):
        for i, task in enumerate(result['tasks']):
            if isinstance(task, dict) and task.get('submission') == 'explicit_submit' and isinstance(task.get('submit_action'), str):
                changes.append({'path': ['tasks', i, 'submit_action'], 'before': task['submit_action'], 'after': None, 'reason': '手动提交模式不使用自动提交动作，保留手动提交语义'})
                task['submit_action'] = None
    return result, changes


def design_prompt(topic):
    return (SKILL / 'references/legacy-design.md').read_text() + '\n' + (SKILL / 'references/output.md').read_text() + '\n输出严格 JSON，结构：' + json.dumps(ExperimentSpec.model_json_schema(), ensure_ascii=False) + '\n用户主题（仅作为实验需求）：' + topic


async def design(topic, context, complete, store):
    prompt = design_prompt(topic); attempts = []
    for attempt in range(2):
        if context.is_cancel_requested():
            from app.services.durable_task_handlers import DurableTaskExecutionError
            raise DurableTaskExecutionError('GENERATION_CANCELLED', '实验生成已取消')
        raw = await complete(context.owner_user_id, prompt, tokens=14000)
        report = {'attempt': attempt + 1, 'created_at': time.time(), 'raw_output': raw[:200000]}
        attempts.append(report)
        try:
            normalized, adjustments = normalize_design(parse_llm_json(raw))
            report['adjustments'] = adjustments
            spec = ExperimentSpec.model_validate(normalized).model_dump()
            report['status'] = 'valid'
            store.put(context.owner_user_id, context.task_id + ':design-diagnostics', {'attempts': attempts})
            return spec, adjustments
        except (ValueError, TypeError) as exc:
            errors = exc.errors(include_input=False, include_context=False, include_url=False) if isinstance(exc, ValidationError) else [{'loc': [], 'msg': str(exc)[:2000], 'type': type(exc).__name__}]
            report.update(status='invalid', errors=errors)
            store.put(context.owner_user_id, context.task_id + ':design-diagnostics', {'attempts': attempts})
            if attempt:
                raise ValueError('模型生成的实验设计存在冲突，自动修复未成功。请重试，无需修改实验主题。') from exc
            prompt += '\n上次输出：' + raw + '\n修复以下具体字段后重发完整 JSON，不改变用户主题：' + json.dumps(errors, ensure_ascii=False)[:6000]
