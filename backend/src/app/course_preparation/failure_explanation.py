"""User-facing failure facts; never publish provider errors or checkpoint text."""
from sqlalchemy import select

from app.database.models import PreparationArtifact
from .tool_registry import digest

STAGES = {'normalize': '理解学习需求', 'ingest': '读取上传资料', 'research_scope': '查找参考资料',
    'plan': '安排学习路径', 'research_nodes': '补充知识点资料', 'produce': '制作学习内容',
    'review': '汇总与检查学习内容', 'repair': '完善学习内容', 'commit': '保存课程'}
PHASES = {'classroom_write': '制作课堂', 'classroom_repair': '完善课堂',
    'resource_write': '制作学习资料', 'resource_review': '检查学习资料'}
KINDS = {'classroom': 'AI 课堂', 'report': '学习报告', 'quiz': '习题'}


def explain(code, stage='', budget_metric=None):
    code = (code or '').split(':', 1)[0]
    if code == 'RESOURCE_REPAIR_FORMAT_INVALID':
        return ('部分习题修正未完成', '系统发现需要修改的内容，但未能把修改正确保存到原题中。',
                '可以重试未完成的内容，已经可用的其他资料不受影响。')
    if code == 'PREPARATION_CONTENT_CONTRACT':
        return ('部分资料整理未完成', '生成的修改未能与原资料正确对应，因此这份资料暂时无法使用。',
                '可以重试未完成的内容，已经可用的其他资料不受影响。')
    if code in ('CONTEXT_BUDGET_EXCEEDED', 'RESEARCH_CONTEXT_BUDGET'):
        return ('一次处理的内容过多', '系统在这一步一次装入的资料或页面内容过多，超过了当前单次处理上限。',
                '直接重试可能再次遇到同样问题。可以先缩小课程范围重新创建，或联系维护人员调整生成方式。')
    if code == 'DEADLINE_EXCEEDED':
        return ('本次准备时间已用完', '课程还没有全部准备好，但本次执行已达到系统设置的时间上限。',
                '可以点击“继续重试”，从已保存的进度继续；若仍反复超时，可减少本次知识点数量。')
    if code == 'BUDGET_EXHAUSTED':
        reason = {'cost_micro_usd': '本次任务剩余的生成额度不足以支付下一步制作的预留费用。',
                  'tokens': '本次任务可处理的文字总量已不足以继续下一步制作。',
                  'calls': '本次任务可使用的生成次数已不足以继续下一步制作。'}.get(budget_metric,
                  '本次制作已达到系统设置的生成额度或执行限制，剩余内容没有完成。')
        return ('本次生成额度不足', reason,
                '重试不会清零已经使用的生成额度。可以减少本次课程范围重新创建，或联系维护人员调整任务额度。')
    if code in ('RESOURCE_CONTENT_REJECTED', 'QUALITY_GATE_FAILED', 'COURSE_CONTRACT_INVALID'):
        return ('部分学习内容仍需修正', '系统检查发现部分内容不够完整或前后不一致，尚未形成可交付的课程。',
                '可以重试，让系统继续完善未完成的内容；如果再次失败，请联系维护人员查看这条任务。')
    if code in ('PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'HARNESS_UNAVAILABLE', 'MODEL_UNAVAILABLE'):
        return ('生成服务暂时没有完成响应', '生成服务响应超时或暂时不可用，本次课程准备已停止。',
                '请稍后点击“继续重试”。已经保存的进度会保留。')
    if code in ('COURSE_REVIEW_UNKNOWN_RESOURCE', 'COURSE_REVIEW_INCOMPLETE', 'COURSE_REVIEW_INVALID', 'MODEL_RESPONSE_INVALID', 'CLASSROOM_BINDINGS_INVALID'):
        return ('生成结果暂时无法继续处理', '生成服务返回的结果不完整或与当前资料不匹配，系统无法继续完成课程。',
                '可以稍后重试；若反复发生，请联系维护人员查看这条任务。')
    if code in ('SOURCE_OR_OWNER_UNAVAILABLE', 'RESOURCE_PERMISSION_DENIED'):
        return ('参考资料暂时无法访问', '本次课程需要的资料已不可用，或当前账号没有访问权限。',
                '请确认资料仍然存在且可以打开，再重试或重新上传资料。')
    if code in ('NO_PROGRESS', 'AGENT_NO_PROGRESS'):
        return ('多次尝试后仍未完成', '系统多次尝试整理或补充内容，但没有取得足够进展，因此停止了本次准备。',
                '可以重试，或把学习目标写得更具体、缩小本次范围后重新创建。')
    return ('课程准备遇到问题', f'任务在“{STAGES.get(stage, "准备课程")}”时中断，目前没有足够信息确认更具体的原因。',
            '请稍后重试；如果再次失败，请联系维护人员查看这条任务。')


def failure_explanation(session, prep, attempt, run):
    if attempt.status != 'failed':
        return None
    title, reason, action = explain(run.error_code, attempt.stage)
    checkpoint = run.checkpoint or {}
    keys = {digest(spec) for spec in checkpoint.get('resource_specs', [])}
    # Do not use the first propagated child error as the only explanation.
    rows = session.scalars(select(PreparationArtifact).where(
        PreparationArtifact.preparation_id == prep.preparation_id,
        PreparationArtifact.owner_user_id == prep.owner_user_id,
        PreparationArtifact.spec_digest.in_(keys)).order_by(PreparationArtifact.artifact_id)).all() if keys else []
    saved = sum(row.status == 'draft' for row in rows)
    issues, seen = [], set()
    for row in rows:
        if row.status != 'failed':
            continue
        detail = (row.content or {}).get('_failure_detail') or {}
        heading, explanation, _ = explain(detail.get('code') or row.error_code, attempt.stage,
                                                   detail.get('budget_metric'))
        item = {'resource_title': row.spec.get('title', '学习内容'),
                'resource_type': KINDS.get(row.resource_type, '学习资料'),
                'step': PHASES.get(detail.get('phase'), '制作学习内容'),
                'reason': explanation}
        issues.append(item)
        if heading not in seen:
            seen.add(heading)
    if issues:
        reason = f'本次有 {len(issues)} 份学习内容未完成：' + '、'.join(sorted(seen)) + '。'
        if len(seen) > 1:
            title = '部分内容生成失败，课程尚未完成'
            action = '请先查看下方各项原因。若涉及生成额度或单次处理上限，直接重试可能仍失败；可缩小课程范围重新创建，或联系维护人员调整。'
    if (run.result_ref or {}).get('course_available'):
        title = '部分内容待补齐，已有资料可以学习'
        action = '可以先进入课程学习已完成的资料，也可以点击“补齐未完成内容”继续处理；已完成资料会保留。'
    return {'title': title, 'reason': reason, 'next_step': action,
            'stage': STAGES.get(attempt.stage, '准备课程'), 'saved_resources': saved,
            'planned_resources': len(keys), 'resource_issues': issues}
