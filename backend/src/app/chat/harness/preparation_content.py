"""Preparation-only content locations and candidate recovery; no planning stage."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy


def value_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def teaching_context(payload):
    context = getattr(payload, 'teaching_context', None)
    if context is None:
        return None
    return context.model_dump(mode='json') if hasattr(context, 'model_dump') else dict(context)


def phase_gateway(gateway, payload, phase):
    preparation = bool(getattr(payload, 'preparation_policy', None) or teaching_context(payload) is not None)
    if not preparation:
        return gateway
    # B owns phase binding and verifies that the runtime is native Harness.
    from app.course_preparation.harness_generation import scoped_gateway
    context = teaching_context(payload)
    return scoped_gateway(gateway, phase=phase,
        context={**context, 'response_format': 'json'} if context is not None else {}, preparation=True)


def generation_failure(code, message, *, category, phase, retry_scope, content_digest=None):
    # F owns the public failure schema. Import lazily to keep old workbench
    # callers usable before the preparation modules are installed.
    from app.course_preparation.generation_failures import FailureDetail, GenerationFailure
    return GenerationFailure(FailureDetail(code=code, message=message, category=category,
        phase=phase, retry_scope=retry_scope, content_digest=content_digest))


CONTENT_INSTRUCTIONS = '''teaching_context 是本次教学规格。原始 request_goal、requirements 优先于偏好；
prior_knowledge 为空表示未知，不能假定已掌握。按 language、depth、desired_outcomes、先修、
learning_activities 和 self_check 展开真实内容，教学顺序必须体现在正文，不能只在说明里承诺。
若要求先例后理，先完整展示一个例子的具体输入、逐步过程和结果，再解释概念或通用伪代码；开头承诺“先看例子”不算已经演示例子。
遵守 exclusions 和 source_policy，只引用已给 evidence；不足就明确指出，不编造依据。
不沿用固定面试模板；只有本次用户明确要求面试才安排面试话术。
node_budget_minutes 是整个节点的时间上限，不是每份资源各自的时长；resource_target_minutes
为空时不自行分配。控制篇幅，正文包含可实际学习的例子、解释和检查。
本次写作直接返回 JSON {"content":原生正文,"applied_requirements":[{"requirement_id":"真实ID",
"locator":定位对象,"explanation":"该位置如何落实要求"}],"objective_bindings":[{"objective_id":"真实ID",
"locator":定位对象,"role":"explanation|practice|check"}]}，不要增加规划调用。
报告 content 为 Markdown，每个二级章节前放 <a id="稳定ID"></a>，locator 为 {"section_id":"该ID"}。
习题 content 使用原生 quiz JSON，题目 id 为稳定 question_id，locator 为 {"question_id":"题目id"}。
习题中对应真实作答题目的目标角色用 practice 或 check；解析属于该题反馈，不把整道题标为 explanation。
requirements 保留整课要求；requirement_ids 是当前节点分工。只标注本资源实际落实的要求，
不要为其他节点重复教学或虚构位置；本节点全部资源合起来必须覆盖 requirement_ids。
绑定具体目标到真正支持它的内容，不能机械给每题绑定所有目标。修订保留未受影响的内容和ID。
习题同时返回 question_time_estimates:[{question_id,thinking_seconds,reason}]，逐题估计独立思考/作答秒数，
不得把节点时间复制为估算；阅读题干、选项和解析的时间由程序另加。reason 解释所需推演步骤和基础。
题量按当前节点时间、目标和其他配套资源控制，不机械生成固定数量。
选择题的 explanation 必须逐项说明每个正确选项和干扰项为何成立或不成立，不能遗漏任何选项。
'''


def parse_envelope(raw):
    value = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip()))
    if not isinstance(value, dict) or 'content' not in value:
        raise ValueError('preparation_content_envelope_missing')
    return value['content'], value


def report_sections(body):
    """Resolve stable markers to nonempty real sections, excluding code fences."""
    sections, current, lines, fenced = {}, None, [], False
    def finish():
        if current is not None:
            prose = '\n'.join(line for line in lines if not re.match(r'^#{1,6}\s', line)).strip()
            if not prose or not any(re.match(r'^##\s+\S', line) for line in lines):
                raise ValueError('preparation_section_has_no_content')
            sections[current] = '\n'.join(lines).strip()
    for line in body.splitlines():
        if re.match(r'^\s*(```|~~~)', line):
            fenced = not fenced
        anchor = r'''<a\s+id=(["'])([A-Za-z0-9_.:-]+)\1></a>'''
        heading = bool(re.match(r'^##\s+\S', line))
        match = (re.search(anchor, line) if heading else re.fullmatch(r'\s*' + anchor + r'\s*', line)) if not fenced else None
        if match:
            finish()
            current, lines = match.group(2), [line] if heading else []
            if current in sections:
                raise ValueError('preparation_duplicate_section_id')
        else:
            lines.append(line)
    finish()
    if not sections:
        raise ValueError('preparation_sections_missing')
    return sections


def resolve_locator(kind, content, locator):
    if not isinstance(locator, dict):
        raise ValueError('preparation_locator_invalid')
    if kind == 'report' and set(locator) == {'section_id'}:
        text = report_sections(content).get(locator['section_id'])
        if text:
            return text
    elif kind == 'quiz' and set(locator) == {'question_id'}:
        for question in content.get('questions', []):
            if question.get('id') == locator['question_id'] and question.get('stem', '').strip() and question.get('explanation', '').strip():
                return question
    elif kind == 'classroom' and set(locator) in ({'scene_id'}, {'scene_id', 'action_id'}):
        for scene in content.get('scenes', []):
            if scene.get('id') != locator['scene_id']:
                continue
            if 'action_id' not in locator and scene.get('content'):
                return scene
            for action in scene.get('actions', []):
                if action.get('id') == locator.get('action_id') and action.get('text', '').strip():
                    return action
    raise ValueError('preparation_locator_not_found_or_empty')


def preparation_metadata(kind, content, envelope, context, spec_digest):
    if not isinstance(spec_digest, str) or not spec_digest:
        raise ValueError('preparation_spec_digest_missing')
    if kind == 'report':
        sections = report_sections(content)
    else:
        sections = {}
    if kind == 'quiz':
        ids = [q.get('id') for q in content['questions']]
        if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('preparation_question_ids_missing_or_duplicate')
    requirements = {r['requirement_id'] for r in context.get('requirements', [])}
    objectives = set(context['objective_ids'])
    applied = envelope.get('applied_requirements')
    bindings = envelope.get('objective_bindings')
    if not isinstance(applied, list) or not isinstance(bindings, list) or not bindings:
        raise ValueError('preparation_bindings_missing')
    found = set()
    for item in applied:
        if item.get('requirement_id') not in requirements or not str(item.get('explanation') or '').strip():
            raise ValueError('preparation_requirement_binding_invalid')
        resolve_locator(kind, content, item.get('locator'))
        found.add(item['requirement_id'])
    if 'requirement_ids' not in context and found != requirements:
        raise ValueError('preparation_requirement_coverage_incomplete')
    for item in bindings:
        if item.get('objective_id') not in objectives or item.get('role') not in {'explanation', 'practice', 'check'}:
            raise ValueError('preparation_objective_binding_invalid')
        resolve_locator(kind, content, item.get('locator'))
    if kind == 'report':
        duration = {'value_minutes': round(max(0.1, len(re.sub(r'\s', '', content)) / 500), 1),
                    'basis': 'estimated', 'method': 'non_whitespace_characters / 500 per minute; reading only, excludes exercises'}
    elif kind == 'quiz' and envelope.get('question_time_estimates'):
        estimates = envelope['question_time_estimates']
        questions = content['questions']
        if (not isinstance(estimates, list) or len(estimates) != len(questions)
                or {e.get('question_id') for e in estimates} != {q['id'] for q in questions}):
            raise ValueError('quiz_time_estimate_coverage_invalid')
        seconds = 0
        for estimate in estimates:
            thinking = estimate.get('thinking_seconds')
            if (isinstance(thinking, bool) or not isinstance(thinking, (int, float))
                    or not 15 <= thinking <= 1800 or len(str(estimate.get('reason', '')).strip()) < 5):
                raise ValueError('quiz_time_estimate_invalid')
            seconds += thinking
        reading = sum(len(re.sub(r'\s', '', str(q.get('stem', '')) + ''.join(q.get('options') or [])
                                + str(q.get('explanation', '')))) for q in questions)
        duration = {'value_minutes': round(seconds / 60 + reading / 500, 2), 'basis': 'estimated',
                    'method': 'per-question model estimate of thinking/answering + stem/options/feedback non-whitespace characters / 500 per minute; not measured or calibrated'}
    else:
        duration = {'value_minutes': None, 'basis': 'unknown', 'method': 'No calibrated learner solving-time estimate'}
    return {'schema_version': 1, 'spec_digest': spec_digest,
            'teaching_context_digest': value_digest(context), 'applied_requirements': applied,
            'objective_bindings': bindings, 'duration': duration,
            **({'question_time_estimates': deepcopy(envelope['question_time_estimates'])} if kind == 'quiz' and envelope.get('question_time_estimates') else {}),
            **({'sections': [{'section_id': key, 'content_sha256': value_digest(text)} for key, text in sections.items()]} if sections else {})}


def validate_preparation_review(content, kind, metadata, checks):
    expected = [(key, item[key], item['locator']) for key, collection in
                [('requirement_id', 'applied_requirements'), ('objective_id', 'objective_bindings')]
                for item in metadata[collection]]
    actual = [(c.binding_type, c.binding_id, c.locator) for c in checks]
    if sorted(map(value_digest, expected)) != sorted(map(value_digest, actual)):
        from collections import Counter
        encode = lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)
        missing = list((Counter(map(encode, expected)) - Counter(map(encode, actual))).elements())
        extra = list((Counter(map(encode, actual)) - Counter(map(encode, expected))).elements())
        raise ValueError('preparation_review_binding_coverage_incomplete: '
                         + json.dumps({'missing': missing, 'extra': extra}, ensure_ascii=False))
    for check in checks:
        resolve_locator(kind, content, check.locator)
    return [f'{c.binding_id} @ {c.locator}: {c.reason}' for c in checks if not c.passed]


class ReviewCandidate:
    """Opaque authorized F port; candidate remains private until review passes."""
    def __init__(self, checkpoint, spec_digest, digest_content):
        self.port, self.spec_digest, self.digest_content = checkpoint, spec_digest, value_digest

    def load(self):
        if self.port is None:
            return None
        candidate = self.port.load_review_candidate()
        if candidate is None:
            return None
        if candidate.get('spec_digest') != self.spec_digest or candidate.get('content_digest') != self.digest_content(candidate.get('content')):
            raise generation_failure('REVIEW_CANDIDATE_CHANGED', '候选正文或规格摘要已变化',
                category='contract', phase='resource_review', retry_scope='none')
        return deepcopy(candidate)

    def save(self, content, state):
        if self.port is not None:
            self.port.save_review_candidate(content=deepcopy(content), content_digest=self.digest_content(content),
                spec_digest=self.spec_digest, review_state=deepcopy(state))
