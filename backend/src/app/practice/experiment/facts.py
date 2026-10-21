"""Deterministic teaching projection of frozen browser evidence, across subjects.

No simulation, model call, state mutation, or inference from generated prose.
Raw records remain available through the evidence tools.
"""
from collections import Counter
from .state_evidence import KEY, state_evidence, completion_reason

VERSION = 'edu-experiment-facts/1'
MISSING = object()
PAGE_TEXT_FIELDS = {'message', 'feedback', 'lastAction', 'explanation', 'narration'}
BOUNDARIES = {'phase_changed', 'phase_entered', 'phase_left', 'initialized',
              'reset', 'replay', 'back', 'demo_restored', 'task_advanced', 'retry_started'}


def read(value, path):
    for key in path:
        if isinstance(value, dict):
            value = value.get(str(key), MISSING)
        elif isinstance(value, list) and str(key).isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return MISSING
    return value


def equal(a, b):
    # JSON booleans are not numbers (unlike Python bool/int equality).
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return type(a) == type(b) and a == b or type(a) in (int, float) and type(b) in (int, float) and a == b


def differences(before, after):
    return [{'field': k, 'before_present': k in before, 'after_present': k in after,
             'before': before.get(k), 'after': after.get(k)}
            for k in sorted(before.keys() | after.keys())
            if k not in before or k not in after or not equal(before[k], after[k])]


def measured_changes(before, after):
    changes = []
    for change in differences(before, after):
        a, b = change['before'], change['after']
        row = {'field': change['field'], 'before_present': change['before_present'], 'after_present': change['after_present']}
        if change['before_present'] and change['after_present'] and type(a) in (int, float) and type(b) in (int, float):
            row.update(before=a, after=b, delta=b-a, direction='increased' if b > a else 'decreased')
        elif isinstance(a, list) and isinstance(b, list):
            row.update(before_length=len(a), after_length=len(b), changed_indices=[i for i in range(min(len(a), len(b))) if not equal(a[i], b[i])])
        else:
            row.update(before=a, after=b)
        changes.append(row)
    return changes


def snapshot_view(context, snapshot_id):
    values = context['snapshots'][snapshot_id]
    return {'snapshot_id': snapshot_id,
            'values': {k: v for k, v in values.items() if k != KEY and not (k in PAGE_TEXT_FIELDS and isinstance(v, str))},
            'state_evidence': state_evidence(values),
            'reference_only': {'page_text': {k: v for k, v in values.items() if k in PAGE_TEXT_FIELDS and isinstance(v, str)},
                               'note': 'Page-written descriptions, not independently verified state causes.'},
            'measurement_validity': 'not_reported; zero is a present value, not evidence of a missing measurement'}


def check_results(checks, state):
    results = []
    for check in checks:
        a = read(state, check['path'])
        b = read(state, check['right_path']) if check.get('right_path') else check.get('value')
        op = check['op']; matched = None
        numeric = type(a) in (int, float) and type(b) in (int, float)
        if a is not MISSING and b is not MISSING:
            if op in ('eq', 'ne'):
                matched = equal(a, b) if op == 'eq' else not equal(a, b)
            elif op == 'contains':
                matched = any(equal(v, b) for v in a) if isinstance(a, list) else isinstance(a, str) and isinstance(b, str) and b in a
            elif numeric:
                matched = {'lt': lambda: a < b, 'lte': lambda: a <= b,
                           'gt': lambda: a > b, 'gte': lambda: a >= b,
                           'near': lambda: abs(a - b) <= check.get('tolerance', 0)}.get(op, lambda: None)()
        results.append({'condition': check, 'actual_present': a is not MISSING,
                        'actual': None if a is MISSING else a, 'expected_present': b is not MISSING,
                        'expected': None if b is MISSING else b, 'matched': matched})
    return results


def kind(event, context=None):
    if event['type'] == 'action':
        command = event.get('command', {})
        declared = (context or {}).get('design', {}).get('actions', []) + (context or {}).get('design', {}).get('action_catalog', [])
        if any(a.get('id') == command.get('action') for a in declared):
            return 'operation'
        return 'control' if set(command.get('input', {})) == {'control', 'value'} else 'operation'
    return 'observation' if event['type'] == 'observation' else 'lifecycle'


def task_definition(context, task_id):
    return next((t for t in context['design'].get('tasks', []) if t['id'] == task_id), None)


def timeline(context):
    """Index semantic operations once; attach assessments only within their scope."""
    events = context['events']; operations = []; assessments = []
    last_assessment = None
    latest = None; attempt_actions = {}; demo_actions = []
    v1 = context['design'].get('protocol') == 'edu-experiment/1'
    for event in events:
        scope = (event['phase'], event.get('task_id'), event.get('attempt_id'))
        if kind(event, context) == 'operation':
            latest = {'event': event, 'assessment': None, 'recovery': None,
                      'assessment_action_ids': [], 'reconstructed': False}
            operations.append(latest)
            attempt_actions.setdefault(scope, []).append(latest)
            if event['phase'] == 'demonstrate':
                demo_actions.append(latest)
        elif event['type'] in ('operation_feedback', 'attempt_submitted'):
            members = attempt_actions.get(scope, [])
            # v1 explicit submission assesses the whole attempt, not each click.
            task = task_definition(context, event.get('task_id')) or {}
            whole_attempt = v1 and task.get('submission') == 'explicit_submit'
            selected = members if whole_attempt else members[-1:]
            assessment = {'event': event, 'actions': selected, 'scope': 'attempt' if whole_attempt else 'operation',
                          'attempt_start': members[0]['event']['before'] if members else None}
            assessment['recovery'] = None
            last_assessment = assessment
            assessments.append(assessment)
            latest = selected[-1] if selected else None
            if latest:
                latest['assessment'] = assessment
                latest['assessment_action_ids'] = [x['event']['id'] for x in selected]
        elif event['type'] == 'retry_started':
            # v1 assigns a new attempt_id before recording recovery; v2 after it.
            if last_assessment and last_assessment['event']['seq'] == event['seq'] - 1:
                last_assessment['recovery'] = event
            if latest and latest['assessment'] and latest['assessment']['event']['seq'] == event['seq'] - 1:
                latest['recovery'] = event
            latest = None
        elif event['type'] in BOUNDARIES:
            latest = None
        if event['type'] == 'demo_restored' and v1:
            # v1 replays apply() to reconstruct a previous screen; these are not
            # additional forward teaching steps or learner operations.
            for operation in demo_actions:
                operation['reconstructed'] = True
        if event['type'] != 'action' and event['type'] != 'observation':
            demo_actions = []
    return operations, assessments


def operation_detail(context, operation):
    e = operation['event']; snapshots = context['snapshots']
    before = snapshots[e['before']]; after = snapshots[e['after']]
    command = e.get('command', {}); inputs = command.get('input', {})
    facts = inputs.get('facts') if isinstance(inputs.get('facts'), dict) else {}
    definitions = context['design'].get('actions', []) + context['design'].get('action_catalog', [])
    definition = next((a for a in definitions if a.get('id') == command.get('action')), {})
    assessment = operation['assessment']; decision = assessment['event'] if assessment else None
    verdict = decision.get('verdict', 'unknown') if decision else 'not_assessed'
    recovery = operation['recovery']
    reason = {'status': 'not_applicable' if verdict != 'fail' else 'unavailable',
              'expected': None, 'actual': None, 'failed_conditions': [],
              'source': 'none', 'learner_misconception': 'not_established_by_operation'}
    task = task_definition(context, e.get('task_id')) or {}
    checks = []
    if assessment and context['design'].get('protocol') == 'edu-experiment/1' and task.get('assessment') == 'deterministic':
        members = assessment['actions']
        first = members[0]['event'] if members else e
        checks = check_results(task.get('checks', []), {
            'before': snapshots[assessment['attempt_start'] or first['before']], 'after': snapshots[decision['after']],
            'input': inputs})
    failed = [c for c in checks if c['matched'] is False]
    if verdict == 'fail' and failed:
        reason.update(status='recorded_condition_mismatch', failed_conditions=failed,
                      source='declared_task_checks_evaluated_on_recorded_snapshots')
    if verdict == 'fail' and not failed and 'expected' in facts and 'chosen' in facts and not equal(facts['expected'], facts['chosen']):
        reason.update(status='reported_choice_mismatch', expected=facts['expected'], actual=facts['chosen'], source='page_reported_action_facts')
    return {
        'operation_id': e['id'], 'seq': e['seq'], 'phase': e['phase'], 'actor': e['actor'],
        'task_id': e.get('task_id'), 'attempt_id': e.get('attempt_id'),
        'action': command.get('action'), 'label': definition.get('label') or command.get('action'),
        'input': {k: v for k, v in inputs.items() if k != 'facts'}, 'reported_facts': facts,
        'before': snapshot_view(context, e['before']),
        'after_action': snapshot_view(context, e['after']),
        'changes': [change for change in measured_changes(before, after) if change['field'] != KEY and not (change['field'] in PAGE_TEXT_FIELDS and isinstance(change['after'] if change['after_present'] else change['before'], str))],
        'assessment': {'verdict': verdict, 'scope': assessment['scope'] if assessment else None,
                       'event_id': decision['id'] if decision else None,
                       'covers_operation_ids': operation['assessment_action_ids'],
                       'checks': checks, 'error_reason': reason,
                       'completion_reason': completion_reason(snapshots[decision['after']] if decision else after)},
        'recovery': {'recorded': bool(recovery), 'event_id': recovery['id'] if recovery else None,
                     'snapshot_id': recovery['after'] if recovery else None,
                     'state_after_recovery': snapshots[recovery['after']] if recovery else None,
                     'restored_operation_start': equal(snapshots[recovery['after']], before) if recovery else None},
        'reference_only': {'action_rule': definition.get('rule') or definition.get('description'),
                           'page_feedback': (decision or e).get('feedback', ''),
                           'warning': 'Generated explanations are not independently verified causes.'},
        'source_event_ids': list(dict.fromkeys([e['id']] + ([decision['id']] if decision else []) + ([recovery['id']] if recovery else []))),
        'reconstructed': operation['reconstructed'],
    }


def choice_match(operation):
    facts = operation['event'].get('command', {}).get('input', {}).get('facts', {})
    if isinstance(facts, dict) and 'expected' in facts and 'chosen' in facts:
        return equal(facts['expected'], facts['chosen'])
    return None


def compact(operation):
    e = operation['event']; decision = operation['assessment']
    return {'operation_id': e['id'], 'seq': e['seq'], 'phase': e['phase'], 'actor': e['actor'],
            'task_id': e.get('task_id'), 'attempt_id': e.get('attempt_id'),
            'action': e.get('command', {}).get('action'),
            'before_snapshot': e['before'], 'after_snapshot': e['after'],
            'reported_facts': e.get('command', {}).get('input', {}).get('facts', {}),
            'verdict': decision['event'].get('verdict', 'unknown') if decision else 'not_assessed',
            'assessment_scope': decision['scope'] if decision else None,
            'choice_matches_page_reported_expectation': choice_match(operation),
            'recovery_recorded': bool(operation['recovery']), 'reconstructed': operation['reconstructed']}


def summary(context, operations=None, assessments=None):
    if operations is None:
        operations, assessments = timeline(context)
    events = context['events']; design = context['design']
    steps = [e for e in events if e['type'] == 'demo_completed'] if design.get('protocol') == 'edu-experiment/1' else [o['event'] for o in operations if o['event']['phase'] == 'demonstrate']
    totals = Counter(kind(e, context) for e in events)
    verdicts = Counter(a['event'].get('verdict', 'unknown') for a in assessments)
    task_rows = []
    for task in design.get('tasks', []):
        records = [a['event'] for a in assessments if a['event'].get('task_id') == task['id']]
        counts = Counter(e.get('verdict', 'unknown') for e in records)
        task_rows.append({'task_id': task['id'], 'title': task['title'], 'phase': 'guided',
                          'recorded_operations': sum(o['event'].get('task_id') == task['id'] and o['event']['actor'] == 'user' for o in operations),
                          'decisions': dict(counts), 'failure_count': counts['fail'],
                          'choices_matching_reported_expectation': sum(choice_match(o) is True for o in operations if o['event'].get('task_id') == task['id']),
                          'choices_mismatching_reported_expectation': sum(choice_match(o) is False for o in operations if o['event'].get('task_id') == task['id']),
                          'pass_count': counts['pass'], 'passed_at_event_ids': [e['id'] for e in records if e.get('verdict') == 'pass'],
                          'ever_passed_in_this_run': counts['pass'] > 0})
    return {'scope': 'entire_frozen_run_including_revisits', 'through_seq': context['state_revision'],
            'raw_events': len(events), 'semantic_operations': totals['operation'],
            'by_phase': {phase: {'semantic_operations': sum(o['event']['phase'] == phase for o in operations),
                                 'user_operations': sum(o['event']['phase'] == phase and o['event']['actor'] == 'user' for o in operations),
                                 'observation_samples': sum(e['phase'] == phase and kind(e, context) == 'observation' for e in events)}
                         for phase in ['demonstrate', 'guided', 'explore']},
            'control_events': totals['control'], 'observation_samples': totals['observation'],
            'lifecycle_events': totals['lifecycle'], 'demonstration_steps_executed': len(steps),
            'demonstration_step_event_ids': [e['id'] for e in steps],
            'reconstruction_operations': sum(o['reconstructed'] for o in operations),
            'user_operations': sum(o['event']['actor'] == 'user' for o in operations),
            'guided_decisions': dict(verdicts), 'tasks': task_rows,
            'counting_rules': {
                'step': 'v1 demo_completed or v2 demonstrate action; excludes initialization, controls, feedback and samples; repeated forward steps count again',
                'operation': 'semantic action; raw DOM control records excluded; an operation is not automatically one algorithm iteration',
                'decision': 'one recorded operation_feedback/attempt_submitted; pending means continue, not independently verified correct; pass means task passed, not every previous operation correct',
                'errors': 'count fail decisions only, not clicks, feedback copies, retries, unknown, or awaiting_review',
                'algorithm_metrics': 'comparison/swap/iteration totals are not inferred from raw event or observation counts'}}


def current_state(context):
    values = context['current_state']; fields = []
    meanings = state_evidence(values)['fields']
    for field in context.get('state_fields', []):
        value = read(values, field['path'])
        fields.append({'path': field['path'], 'label': field.get('label'), 'unit': field.get('unit', ''),
                       'description': field.get('description', ''), 'present': value is not MISSING,
                       'source': 'page_text_reference' if field['path'][0] in PAGE_TEXT_FIELDS and isinstance(value, str) else 'snapshot_field_not_measurement_validation',
                       'value': None if value is MISSING else value,
                       'semantics': next((m for m in meanings if m['path'] == field['path']), None)})
    task = task_definition(context, context.get('task_id'))
    return {'phase': context['phase'], 'task_id': context.get('task_id'),
            'task_title': task.get('title') if task else None,
            'task_scope_note': '当前处于自由探索，没有当前动手任务；未通过的设计任务不等于当前任务' if context['phase'] == 'explore' else '当前任务与所问历史操作的任务分别定位',
            'step_index': context.get('step_index'), 'reported_verdict': context.get('verdict'),
            'attempt_id': context['attempt_id'], 'snapshot_id': str(context['state_revision']),
            **snapshot_view(context, str(context['state_revision'])), 'fields': fields,
            'completion_reason': completion_reason(values),
            'state_string_fields_are_page_reported': True}


def recorded_completions(context):
    """Keep actual completed episodes accessible after reset/parameter changes.

    Repeated timer samples and recovery/replay are not new completions. Only
    explicit page-reported completion evidence is used, never a guessed flag.
    """
    records = []
    for event in context['events']:
        if event['type'] not in ('action', 'observation'):
            continue
        before = completion_reason(context['snapshots'][event['before']])
        after = completion_reason(context['snapshots'][event['after']])
        if not isinstance(after, dict) or after['status'] != 'complete' or equal(before, after):
            continue
        records.append({'event_id': event['id'], 'seq': event['seq'], 'phase': event['phase'],
                        'task_id': event.get('task_id'), 'attempt_id': event.get('attempt_id'),
                        'snapshot_id': event['after'], 'completion': after,
                        'values': snapshot_view(context, event['after'])['values']})
    return {'items': records[-4:], 'total': len(records), 'details_partial': len(records) > 4,
            'scope': 'reported_completion_transitions_in_frozen_run; not_current_completion_after_reset',
            'missing_is_not_proof_no_completion_occurred': True}


def fact_packet(context, focus):
    operations, assessments = timeline(context)
    selected = next((o for o in operations if focus and o['event']['id'] == focus['id']), None)
    if selected:
        target = {'kind': 'operation', **operation_detail(context, selected)}
    elif focus and focus['type'] == 'attempt_submitted':
        assessment = next(a for a in assessments if a['event']['id'] == focus['id'])
        synthetic = {'event': focus, 'assessment': assessment, 'assessment_action_ids': [o['event']['id'] for o in assessment['actions']],
                     'recovery': assessment['recovery'], 'reconstructed': False}
        target = {'kind': 'assessment', **operation_detail(context, synthetic)}
        target['operation_id'] = None
        target['event_id'] = focus['id']
        target['label'] = '提交尝试'
    elif focus:
        target = {'kind': kind(focus, context), 'event_id': focus['id'], 'type': focus['type'],
                  'phase': focus['phase'], 'actor': focus['actor'],
                  'before': snapshot_view(context, focus['before']),
                  'after_action': snapshot_view(context, focus['after']),
                  'assessment': None, 'note': 'Not a semantically assessed operation.'}
    else:
        target = None
    previous = next((o for o in reversed(operations) if focus and o['event']['seq'] < focus['seq'] and not o['reconstructed']), None)
    # This is recorded history, never a forecast. Do not cross task/phase/retry boundaries.
    following = None
    if selected:
        for o in operations:
            e = o['event']
            if e['seq'] <= focus['seq']:
                continue
            between = context['events'][focus['seq']:e['seq'] - 1]
            if e['phase'] == focus['phase'] and e.get('attempt_id') == focus.get('attempt_id') and not any(x['type'] in BOUNDARIES for x in between):
                following = {**compact(o), 'reported_facts': e.get('command', {}).get('input', {}).get('facts', {}),
                             'source': 'actually_recorded_after_focus_not_a_prediction'}
            break
    focus_counts = None
    subsequent_operations = []
    if selected:
        later = []
        for event in context['events'][focus['seq']:]:
            if event['type'] in {'phase_changed', 'phase_entered', 'phase_left', 'reset', 'initialized', 'task_advanced', 'replay', 'back', 'demo_restored'}:
                break
            if kind(event, context) == 'operation' and event['phase'] == focus['phase'] and event.get('task_id') == focus.get('task_id'):
                later.append(event['id'])
                op = next(o for o in operations if o['event']['id'] == event['id'])
                subsequent_operations.append(compact(op))
        focus_counts = {'scope': 'recorded_after_focus_until_next_task_initialization_reset_or_phase_boundary',
                        'semantic_operations_after_focus': len(later), 'operation_ids': later,
                        'operations': subsequent_operations[:12],
                        'operations_list_partial': len(subsequent_operations) > 12,
                        'excludes_focus_itself': True, 'not_a_forecast': True}
    mistakes = []
    for assessment in assessments:
        if assessment['event'].get('verdict') == 'fail':
            operation = assessment['actions'][-1] if assessment['actions'] else {
                'event': assessment['event'], 'assessment': assessment, 'assessment_action_ids': [],
                'recovery': assessment['recovery'], 'reconstructed': False}
            detail = operation_detail(context, operation)
            mistakes.append({'operation_id': detail['operation_id'] if assessment['actions'] else None,
                             'task_id': detail['task_id'],
                             'decision_event_id': detail['assessment']['event_id'],
                             'assessment_scope': detail['assessment']['scope'],
                             'error_reason': detail['assessment']['error_reason'],
                             'recovery_recorded': detail['recovery']['recorded']})
    totals = summary(context, operations, assessments)
    statements = [
        '当前阶段：' + {'demonstrate': '原理演示', 'guided': '动手实践', 'explore': '自由探索'}[context['phase']],
        '当前动手任务：' + ((task_definition(context, context.get('task_id')) or {}).get('title', '无')),
        f"系统演示累计执行 {totals['demonstration_steps_executed']} 步；初始化、回看重建、控件点击、反馈和动画采样均不算演示步骤。",
        '任务统计仅属于动手实践阶段，即使任务标题含有“自由探索”，也不代表自由探索阶段；自由探索阶段单独统计。',
        f"自由探索阶段实际记录 {totals['by_phase']['explore']['user_operations']} 次用户实验动作、{totals['by_phase']['explore']['observation_samples']} 条状态采样；不是动手任务操作次数，也不能换算为比较/交换次数。",
        '快照有数值不等于真实测量已经验证；数值为 0 也不等于未测量。本记录没有测量有效性标记，不确定的要说明不确定。',
        '状态标记只说明快照当时的值。false/0 可能是操作后重置值，不能证明此前没有交换、事件或测量；缺少字段作用范围、重置规则和结束原因时，不推断必然多执行了某一轮。',
        '下列动作数已经去除点击、判定和回滚等重复记录；判定是动作的结果，不能再加进动作次数。',
    ]
    for t in totals['tasks']:
        counts = t['decisions']
        statements.append(f"动手阶段任务「{t['title']}」：累计 {t['recorded_operations']} 次实验动作；对应判定中失败 {t['failure_count']} 次、任务通过 {t['pass_count']} 次、继续 {counts.get('pending', 0)} 次。选择符合页面记录预期 {t['choices_matching_reported_expectation']} 次、不符合 {t['choices_mismatching_reported_expectation']} 次；没有上报预期的动作不归入这两个选择计数。")
    if focus_counts and focus_counts['semantic_operations_after_focus'] == 0:
        statements.append('这个冻结时点没有记录所问动作之后的新动作。未被要求预测时，只解释当前变化和未完成的条件，不列出多步未来数值。')
    if focus_counts:
        statements.append(f"所问动作之后、下一次任务初始化/重置/阶段切换之前实际又记录了 {focus_counts['semantic_operations_after_focus']} 次实验动作，不含所问动作本身。这些是历史记录，不是未来预测。")
    return {'schema': VERSION, 'source': 'browser_reported_with_deterministic_projection',
            'scientifically_verified': False, 'current': current_state(context), 'focus': target,
            'recorded_next_operation': following, 'after_focus_counts': focus_counts,
            'recorded_completions': recorded_completions(context),
            'recent_mistakes': mistakes[-3:], 'mistakes_total': len(mistakes),
            'previous_operation_id': previous['event']['id'] if previous else None,
            'totals': totals, 'record_summary': statements,
            'recent_operations': [compact(o) for o in operations[-6:]],
            'coverage': {'raw_events': len(context['events']), 'operations_total': len(operations),
                         'operations_in_recent_list': min(6, len(operations)),
                         'totals_cover_full_frozen_run': True,
                         'history_details_partial': len(operations) > 6,
                         'tools': ['list_operations', 'get_operation', 'get_fact_summary']}}
