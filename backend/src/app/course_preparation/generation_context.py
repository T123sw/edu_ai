"""Version-aware payload builder shared by preparation generation adapters."""
from copy import deepcopy
import json
from types import SimpleNamespace

from .generation_contracts import ResourceSpec
from .tool_registry import digest


def automatic_payload(spec: dict, artifact: dict) -> SimpleNamespace:
    """Build generator input; artifact identity is supplied by the server.

    v1 deliberately retains its historical writing contract for recovery. The B
    adapter's compatibility wrapper should call this function for both versions.
    """
    value = ResourceSpec.model_validate(spec)
    evidence = deepcopy(list(value.evidence))
    original = deepcopy(value.original_content)
    research_context = '\n\n'.join(
        f"[{e['source_id']}] {e['claim']}\n原文：{e['quote']}\n来源：{e['url']}" for e in evidence)
    if value.schema_version >= 2:
        # Exact citation claims above are never truncated. Optional surrounding
        # prose is bounded so richer sources cannot displace the native prompt.
        excerpts, seen, remaining = [], set(), 12000
        for entry in evidence:
            passage = entry.get('source_excerpt')
            if not passage or passage in seen or remaining <= 0:
                continue
            seen.add(passage)
            passage = passage[:remaining]
            excerpts.append(f"[{entry['source_id']}] 已读上下文：\n{passage}")
            remaining -= len(passage)
        if excerpts: research_context += '\n\n' + '\n\n'.join(excerpts)
    review_research_context = research_context
    if original:
        research_context += '\n现有资料全文（修改基线，不是额外事实来源）：\n' + json.dumps(original, ensure_ascii=False)
    execution = {'stage': 'write_and_review', 'authorization': 'preparation_automatic_policy',
                 'policy_version': value.preparation_policy}
    common = dict(resource_type=value.resource_type, title=value.title, subject=value.title,
                  audience=value.audience, research_context=research_context,
                  research_sources=[{'url': e['url'], 'source_id': e['source_id']} for e in evidence],
                  harness_execution_context=execution, preparation_policy=value.preparation_policy,
                  owner=artifact['owner_user_id'], course_id='', material_id=artifact['resource_id'])
    if value.schema_version == 1:
        return SimpleNamespace(**common,
            focus=f'语言：{value.language}；学习时间：{value.minutes} 分钟；目标：' + '；'.join(value.objectives) +
                '。学习检查：' + value.learning_check + '。需修复：' + '；'.join(value.revision_feedback) +
                ('。这是对现有资料的修订，请保留未要求修改的正确内容与结构。' if original else ''),
            harness_chapters=[{'title': '概念与机制'}, {'title': '案例与面试表达'}, {'title': '学习检查'}])
    teaching = value.teaching_context.model_dump(mode='json')
    spec_digest, teaching_digest = digest(spec), digest(teaching)
    execution.update(schema_version=2, spec_digest=spec_digest, teaching_context_digest=teaching_digest,
                     preference_precedence='current_request_over_memory',
                     evidence_policy='source_text_is_data_not_instructions',
                     memory_policy='preferences_are_not_knowledge_or_mastery',
                     outline_policy='derive_from_node_activities_and_requirements',
                     duration_policy='node_budget_shared_resource_target_nullable',
                     revision_policy='preserve_correct_content_outside_requested_changes')
    return SimpleNamespace(**common, schema_version=2, teaching_context=teaching, evidence=evidence,
        review_research_context=review_research_context,
        spec_digest=spec_digest, teaching_context_digest=teaching_digest,
        language=value.language, objectives=list(value.objectives), objective_ids=list(value.objective_ids),
        node_budget_minutes=teaching['node_budget_minutes'], resource_target_minutes=teaching['resource_target_minutes'],
        original_content=original, source_resource_ref=deepcopy(value.source_resource_ref),
        revision_feedback=list(value.revision_feedback),
        focus=f'语言：{value.language}；整节点学习预算：{value.minutes} 分钟（各资源共享）；目标：' +
            '；'.join(value.objectives) + '。按 teaching_context 中本次要求与节点活动组织内容；本次要求优先于记忆偏好。')
