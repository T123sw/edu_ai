from copy import deepcopy
import pytest
from app.practice.experiment.facts import fact_packet
from app.practice.experiment.teaching import EvidenceRequest, read_evidence
from app.practice.experiment.state_evidence import state_evidence, VERSION
from tests.practice.test_experiment_facts import context, append


def measured_state():
    # Non-algorithm example: cycle-local threshold flag cleared at trial end.
    return {'thresholdReached': False, 'trial': 3, 'distance': 0, '_teaching': {
        'version': VERSION,
        'fields': [{'path': ['thresholdReached'], 'meaning': '本次周期阈值标记',
                    'scope': '当前测量周期', 'reset_when': '测量周期末复位，不代表未达到阈值'}],
        'transition': {'id': 'cycle-3', 'kind': 'cycle_end', 'observations': {'trialEnded': 3},
                       'resets': [{'path': ['thresholdReached'], 'before': True, 'after': False, 'reason': '周期结束'}]},
        'completion': {'status': 'complete', 'code': 'trial_limit', 'reason': '已完成三次试验',
                       'basis': {'trialsCompleted': 3}}}}


def test_reset_values_and_completion_remain_distinct_from_snapshot_flags():
    c = context(); e = append(c, 'observation', state=measured_state(), phase='explore', task=None)
    original = deepcopy(c); f = fact_packet(c, e)
    assert f['current']['values']['thresholdReached'] is False
    assert '_teaching' not in f['current']['values']
    evidence = f['current']['state_evidence']
    assert evidence['last_transition']['resets'][0]['before'] is True
    assert f['current']['completion_reason']['code'] == 'trial_limit'
    assert f['current']['completion_reason']['source'] == 'page_reported_not_independently_verified'
    assert f['current']['values']['distance'] == 0
    assert c == original


def test_repeated_transition_in_samples_is_not_an_extra_action():
    c = context()
    for n in range(3): append(c, 'observation', state={**measured_state(), 'timer': n}, phase='explore', task=None)
    f = fact_packet(c, c['events'][-1])
    assert f['totals']['semantic_operations'] == 0 and f['totals']['observation_samples'] == 3
    assert f['current']['state_evidence']['last_transition']['id'] == 'cycle-3'


def test_reset_does_not_carry_previous_completion_into_current_or_erase_history():
    c = context(); e = append(c, 'observation', state=measured_state(), phase='explore', task=None)
    append(c, 'initialized', state={'trial': 0, '_teaching': {'version': VERSION, 'completion': None, 'transition': None}}, phase='explore', task=None)
    f = fact_packet(c, e)
    assert f['current']['completion_reason'] == 'not_reported_as_structured_evidence'
    assert f['focus']['after_action']['state_evidence']['completion']['code'] == 'trial_limit'


@pytest.mark.parametrize('raw', [None, 7, {'version': 'future/1'}, {'version': VERSION, 'completion': {'status': 'complete'}}])
def test_legacy_or_invalid_metadata_is_unknown_not_request_failure(raw):
    c = context(); e = append(c, 'observation', state={'flag': False, 'lastAction': '无变化结束', '_teaching': raw})
    f = fact_packet(c, e)
    assert f['current']['completion_reason'] == 'not_reported_as_structured_evidence'
    assert f['current']['state_evidence']['interpretation_limits']
    assert f['current']['values']['flag'] is False


def test_bad_completion_does_not_discard_field_semantics():
    s = measured_state(); s['_teaching']['completion'] = {'status': 'complete', 'code': 4}
    result = state_evidence(s)
    assert len(result['fields']) == 1 and result['last_transition']['resets'][0]['before'] is True
    assert result['completion'] is None and result['completion_status'] == 'invalid'


def test_semantics_do_not_replace_observed_values_and_survive_evidence_tools():
    c = context(); c['state_fields'] = [{'path': ['thresholdReached'], 'label': '阈值标记'}]
    state = measured_state(); e = append(c, 'action', state=state, command={'action': 'set', 'input': {}})
    append(c, 'attempt_submitted', verdict='pass')
    summary = read_evidence(c, EvidenceRequest(tool='get_fact_summary'))['result']
    assert summary['current']['fields'][0]['value'] is False
    assert summary['current']['fields'][0]['semantics']['scope'] == '当前测量周期'
    detail = read_evidence(c, EvidenceRequest(tool='get_operation', operation_id=e['id']))['result']
    assert detail['assessment']['completion_reason']['code'] == 'trial_limit'
    assert all(change['field'] != '_teaching' for change in detail['changes'])
    raw = read_evidence(c, EvidenceRequest(tool='get_snapshot', snapshot_id=e['after']))['result']
    assert raw == state


def test_previous_completion_keeps_its_own_cause_and_counts_after_reset():
    c = context(); s = measured_state(); s['comparisons'] = 6
    first = append(c, 'observation', state=s, phase='explore', task=None)
    append(c, 'observation', state={**s, 'running': False}, phase='explore', task=None)
    append(c, 'initialized', state={'trial': 0}, phase='explore', task=None)
    next_state = measured_state(); next_state['_teaching']['completion'].update(code='no_change', reason='本轮无变化')
    next_state['comparisons'] = 3
    last = append(c, 'observation', state=next_state, phase='explore', task=None)
    history = fact_packet(c, last)['recorded_completions']
    assert history['total'] == 2
    assert history['items'][0]['event_id'] == first['id']
    assert [x['completion']['code'] for x in history['items']] == ['trial_limit', 'no_change']
    assert [x['values']['comparisons'] for x in history['items']] == [6, 3]
    assert read_evidence(c, EvidenceRequest(tool='get_fact_summary'))['result']['recorded_completions'] == history
