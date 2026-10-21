from copy import deepcopy
import pytest
from app.practice.experiment.facts import fact_packet, timeline, operation_detail, summary
from app.practice.experiment.teaching import EvidenceRequest, read_evidence


def context(protocol='edu-experiment/2'):
    return {'context_version': 'edu-experiment-context/1', 'context_id': 'ctx', 'revision': 'rev',
            'run_id': 'run', 'state_revision': 0, 'phase': 'guided', 'task_id': 't', 'attempt_id': 'a',
            'current_state': {'value': 1}, 'snapshots': {'0': {'value': 1}}, 'events': [],
            'evidence_source': 'browser_reported', 'state_fields': [
                {'path': ['value'], 'label': '测量值', 'unit': 'N'},
                {'path': ['missing'], 'label': '未上报量'}],
            'design': {'protocol': protocol, 'actions': [], 'demo_steps': [],
                       'action_catalog': [{'id': 'set', 'label': '选择参数', 'rule': '按任务要求选择'}],
                       'tasks': [{'id': 't', 'title': '任务一'}, {'id': 'next', 'title': '任务二'}]}}


def append(c, kind, *, state=None, phase='guided', task='t', attempt='a', actor='user', **extra):
    seq = len(c['events']) + 1
    event = dict(id=f'e{seq}', seq=seq, type=kind, actor=actor, phase=phase, task_id=task,
                 attempt_id=attempt, before=f'{seq}:before', after=str(seq), **extra)
    c['snapshots'][event['before']] = deepcopy(c['current_state'])
    c['current_state'] = deepcopy(state if state is not None else c['current_state'])
    c['snapshots'][event['after']] = deepcopy(c['current_state'])
    c['events'].append(event); c['state_revision'] = seq; c['phase'] = phase
    c['task_id'] = task; c['attempt_id'] = attempt
    return event


def action(c, **kw):
    return append(c, 'action', command={'action': 'set', 'input': {'facts': {'expected': 2, 'chosen': 1}}}, **kw)


def test_dom_feedback_retry_do_not_duplicate_operations_or_failures():
    c = context(); append(c, 'initialized', actor='system')
    append(c, 'action', command={'action': '点击', 'input': {'control': 'button', 'value': ''}})
    failed = action(c, state={'value': 9})
    append(c, 'attempt_submitted', verdict='fail', feedback='错误解释不当作事实')
    append(c, 'retry_started', state={'value': 1}, actor='system')
    c['attempt_id'] = 'retry'
    original = deepcopy(c); f = fact_packet(c, failed)
    assert f['totals']['semantic_operations'] == 1
    assert f['totals']['control_events'] == 1
    assert f['totals']['tasks'][0]['failure_count'] == 1
    op = f['focus']; assert op['before']['values'] == {'value': 1}
    assert op['after_action']['values'] == {'value': 9}
    assert op['recovery']['state_after_recovery'] == {'value': 1}
    assert op['recovery']['restored_operation_start'] is True
    assert op['assessment']['error_reason']['expected'] == 2
    assert op['assessment']['error_reason']['actual'] == 1
    assert f['current']['fields'][0]['unit'] == 'N'
    assert f['current']['fields'][1]['present'] is False
    assert c == original


def test_demo_step_counts_exclude_initialization_and_samples():
    c = context(); append(c, 'initialized', phase='demonstrate', task=None, actor='system')
    for _ in range(6): action(c, phase='demonstrate', task=None, actor='system')
    append(c, 'observation', phase='explore', task=None, actor='system')
    s = summary(c)
    assert s['demonstration_steps_executed'] == 6
    assert s['observation_samples'] == 1 and s['user_operations'] == 0


def test_v1_multiple_commands_and_reconstruction_are_not_forward_steps():
    c = context('edu-experiment/1')
    for _ in range(2): action(c, phase='demonstrate', task=None, actor='system')
    append(c, 'demo_completed', phase='demonstrate', task=None, actor='system')
    action(c, phase='demonstrate', task=None, actor='system')
    append(c, 'demo_restored', phase='demonstrate', task=None)
    assert summary(c)['demonstration_steps_executed'] == 1
    assert summary(c)['reconstruction_operations'] == 1


def test_pass_followed_by_next_task_does_not_replace_completed_result():
    c = context(); e = action(c, state={'value': 2})
    append(c, 'attempt_submitted', verdict='pass')
    append(c, 'initialized', task='next', attempt='next-attempt', state={'value': 0}, actor='system')
    f = fact_packet(c, e)
    assert f['focus']['assessment']['verdict'] == 'pass'
    assert f['focus']['after_action']['values'] == {'value': 2}
    assert f['current']['task_id'] == 'next' and f['current']['values'] == {'value': 0}
    assert f['totals']['tasks'][0]['ever_passed_in_this_run']
    assert not f['totals']['tasks'][1]['ever_passed_in_this_run']
    assert f['recorded_next_operation'] is None


def test_v1_explicit_submit_reason_applies_to_whole_attempt_and_new_retry_id():
    c = context('edu-experiment/1'); t = c['design']['tasks'][0]
    t.update(submission='explicit_submit', assessment='deterministic', checks=[
        {'path': ['after', 'value'], 'op': 'gte', 'value': 5},
        {'path': ['before', 'value'], 'op': 'eq', 'value': 1}])
    first = action(c, state={'value': 2}); last = action(c, state={'value': 3})
    append(c, 'attempt_submitted', verdict='fail')
    append(c, 'retry_started', state={'value': 1}, attempt='new')
    f = fact_packet(c, last)['focus']
    assert f['assessment']['scope'] == 'attempt'
    assert f['assessment']['covers_operation_ids'] == [first['id'], last['id']]
    assert len(f['assessment']['error_reason']['failed_conditions']) == 1
    assert f['assessment']['error_reason']['failed_conditions'][0]['actual'] == 3
    assert f['recovery']['recorded'] and not f['recovery']['restored_operation_start']
    assert fact_packet(c, first)['focus']['assessment']['verdict'] == 'not_assessed'


@pytest.mark.parametrize('verdict', ['unknown', 'awaiting_review', 'pending'])
def test_unknown_review_and_pending_do_not_become_errors_or_passes(verdict):
    c = context(); e = action(c); append(c, 'attempt_submitted', verdict=verdict)
    f = fact_packet(c, e)
    assert f['totals']['tasks'][0]['failure_count'] == 0
    assert f['totals']['tasks'][0]['pass_count'] == 0
    assert f['focus']['assessment']['error_reason']['status'] == 'not_applicable'


def test_unreported_error_cause_not_invented_from_feedback():
    c = context(); e = append(c, 'action', command={'action': 'set', 'input': {}})
    append(c, 'attempt_submitted', verdict='fail', feedback='用户没有理解原理')
    reason = fact_packet(c, e)['focus']['assessment']['error_reason']
    assert reason['status'] == 'unavailable'
    assert reason['learner_misconception'] == 'not_established_by_operation'


def test_observation_is_not_assessed_operation_and_completion_cause_not_guessed():
    c = context(); e = append(c, 'observation', phase='explore', task=None,
                             state={'done': True, 'lastAction': '无交换结束'})
    f = fact_packet(c, e)
    assert f['focus']['kind'] == 'observation' and f['focus']['assessment'] is None
    assert f['totals']['semantic_operations'] == 0
    assert f['current']['completion_reason'] == 'not_reported_as_structured_evidence'


def test_paged_operation_tools_read_full_frozen_history_and_reject_other_ids():
    c = context()
    for _ in range(9): action(c)
    first = read_evidence(c, EvidenceRequest(tool='list_operations', limit=2))['result']
    assert len(first['items']) == 2 and first['has_more']
    second = read_evidence(c, EvidenceRequest(tool='list_operations', after_seq=first['next_seq']))['result']
    assert len(second['items']) == 7 and not second['has_more']
    assert read_evidence(c, EvidenceRequest(tool='get_operation', operation_id='e1'))['result']['before']['values'] == {'value': 1}
    assert read_evidence(c, EvidenceRequest(tool='get_fact_summary'))['result']['totals']['semantic_operations'] == 9
    with pytest.raises(ValueError): read_evidence(c, EvidenceRequest(tool='get_operation', operation_id='foreign'))
    assert fact_packet(c, c['events'][-1])['coverage']['history_details_partial']


def test_next_recorded_operation_is_not_forecast_and_does_not_cross_retry():
    c = context(); first = action(c, state={'value': 2}); second = action(c, state={'value': 3})
    assert fact_packet(c, first)['recorded_next_operation']['before_snapshot'] == second['before']
    append(c, 'attempt_submitted', verdict='fail'); append(c, 'retry_started', state={'value': 2})
    action(c, attempt='new')
    assert fact_packet(c, second)['recorded_next_operation'] is None


def test_counts_after_focus_exclude_itself_and_stop_at_next_task():
    c = context(); first = action(c)
    for _ in range(5): action(c)
    append(c, 'attempt_submitted', verdict='pass')
    append(c, 'initialized', task='next', attempt='new')
    action(c, task='next', attempt='new')
    f = fact_packet(c, first)
    assert f['after_focus_counts']['semantic_operations_after_focus'] == 5
    assert f['totals']['tasks'][0]['recorded_operations'] == 6


def test_checks_use_attempt_start_even_when_only_last_action_triggers_assessment():
    c = context('edu-experiment/1'); c['design']['tasks'][0].update(
        submission='on_action', assessment='deterministic', checks=[
            {'path': ['after', 'value'], 'op': 'gt', 'right_path': ['before', 'value']}])
    action(c, state={'value': 10}); last = action(c, state={'value': 5})
    append(c, 'attempt_submitted', verdict='pass')
    check = fact_packet(c, last)['focus']['assessment']['checks'][0]
    assert check['actual'] == 5 and check['expected'] == 1 and check['matched'] is True


def test_choice_comparison_is_separate_from_pass_and_not_guessed_for_missing_facts():
    c = context(); action(c)
    append(c, 'attempt_submitted', verdict='fail'); append(c, 'retry_started')
    append(c, 'action', command={'action': 'set', 'input': {'facts': {'expected': False, 'chosen': False}}})
    append(c, 'operation_feedback', verdict='pending')
    append(c, 'action', command={'action': 'other', 'input': {}})
    s = summary(c)['tasks'][0]
    assert s['choices_matching_reported_expectation'] == 1
    assert s['choices_mismatching_reported_expectation'] == 1
    assert s['recorded_operations'] == 3 and s['pass_count'] == 0


def test_submit_without_action_retains_failed_condition_and_recovery():
    from app.practice.experiment.tutor import choose_focus
    c = context('edu-experiment/1'); c['design']['tasks'][0].update(
        submission='explicit_submit', assessment='deterministic', checks=[{'path': ['after', 'value'], 'op': 'eq', 'value': 3}])
    append(c, 'phase_entered'); decision = append(c, 'attempt_submitted', verdict='fail')
    append(c, 'retry_started', attempt='retry')
    assert choose_focus(c)['id'] == decision['id']
    f = fact_packet(c, choose_focus(c)); target = f['focus']
    assert target['kind'] == 'assessment' and target['operation_id'] is None
    assert target['assessment']['error_reason']['failed_conditions'][0]['actual'] == 1
    assert target['recovery']['recorded']
    assert f['totals']['semantic_operations'] == 0 and f['totals']['tasks'][0]['failure_count'] == 1
    assert f['mistakes_total'] == 1


def test_numeric_change_direction_does_not_follow_expected_theory_or_zero_sentinel():
    c = context(); c['current_state'] = {'distance': 0}; c['snapshots']['0'] = {'distance': 0}
    e = action(c, state={'distance': 2.04})
    change = fact_packet(c, e)['focus']['changes'][0]
    assert change == {'field': 'distance', 'before_present': True, 'after_present': True,
                      'before': 0, 'after': 2.04, 'delta': 2.04, 'direction': 'increased'}


def test_declared_action_control_parameter_is_not_mistaken_for_dom_event():
    c = context(); e = append(c, 'action', command={'action': 'set', 'input': {'control': 'force', 'value': 3}})
    f = fact_packet(c, e)
    assert f['focus']['kind'] == 'operation' and f['totals']['control_events'] == 0


def test_task_title_does_not_change_phase_or_exploration_counts():
    c = context(); c['design']['tasks'][1]['title'] = '自由探索'
    action(c, phase='explore', task=None)
    f = fact_packet(c, c['events'][-1])
    assert f['current']['phase'] == 'explore' and f['current']['task_id'] is None
    assert f['totals']['by_phase']['explore']['user_operations'] == 1
    assert f['totals']['tasks'][1]['phase'] == 'guided' and f['totals']['tasks'][1]['recorded_operations'] == 0


def test_page_explanation_is_separate_from_numerical_state():
    c = context(); e = action(c, state={'value': 2, 'lastAction': '没有变化', 'message': '示例'})
    f = fact_packet(c, e)
    assert f['current']['values'] == {'value': 2}
    assert f['current']['reference_only']['page_text']['lastAction'] == '没有变化'
    assert f['focus']['changes'][0]['direction'] == 'increased'
    assert c['snapshots'][e['after']]['lastAction'] == '没有变化'
