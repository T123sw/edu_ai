"""G acceptance infrastructure contracts; these tests never claim live model success."""
import json
from pathlib import Path

import pytest

from scripts.preparation_validation_common import database_identity, local_http, redact
from scripts.verify_preparation_full_e2e import assert_harness_receipts, assert_outcome, main


def completion(**changes):
    response = {'runtime': 'deepseek-harness', 'phase': 'resource_review', 'spec_digest': 'a'*64,
        'skill': {'name': 'review-learning-resource', 'sha256': 'b'*64, 'loaded': True},
        'provider': 'deepseek', 'model': 'test-model'}
    response.update(changes)
    return {'kind': 'model_completion', 'status': 'completed',
            'receipt': {'model_response': response, 'usage': {'reported_by_provider': True, 'tokens': 42}}}


@pytest.mark.parametrize('url', ['sqlite:///test.db', 'postgresql://u:p@localhost/business',
    'postgresql://u:p@localhost/edu_ai_preparation_test_a?options=-csearch_path=public', '',
    'postgresql://u:p@localhost/edu_ai_preparation_test_'])
def test_database_guard_rejects_unsafe_targets_without_connecting(url):
    with pytest.raises(ValueError):
        database_identity(url)


def test_database_identity_contains_no_credentials():
    first = database_identity('postgresql+psycopg://u:secret@127.0.0.1:55447/edu_ai_preparation_test_g')
    second = database_identity('postgresql://different:other@127.0.0.1:55447/edu_ai_preparation_test_g')
    assert first == second
    assert 'secret' not in json.dumps(first)


@pytest.mark.parametrize('url', ['https://example.com', 'http://u:p@127.0.0.1:8027', 'http://localhost:8027/api', 'http://localhost:8027?token=secret'])
def test_http_guard_rejects_non_dedicated_target(url):
    with pytest.raises(ValueError):
        local_http(url)


@pytest.mark.parametrize('changes', [dict(runtime='direct'), dict(phase=''), dict(spec_digest=''),
    dict(skill={'name': 'review', 'sha256': 'b'*64, 'loaded': False})])
def test_every_model_completion_requires_real_harness_receipt(changes):
    with pytest.raises(AssertionError):
        assert_harness_receipts([completion(), completion(**changes)])


def test_failed_provider_attempt_is_recorded_but_not_a_completion():
    failed = completion(); failed['status'] = 'failed'; failed['receipt'] = None
    assert assert_harness_receipts([failed, completion()]) == 1
    with pytest.raises(AssertionError, match='NO_REAL_MODEL'):
        assert_harness_receipts([failed])


def test_missing_provider_usage_cannot_pass():
    action = completion(); action['receipt']['usage']['reported_by_provider'] = False
    with pytest.raises(AssertionError, match='REAL_USAGE_MISSING'):
        assert_harness_receipts([action])


def test_expected_business_failure_is_distinct_from_test_failure():
    case = {'expected_business_status': 'failed', 'expected_error_code': 'RESEARCH_INSUFFICIENT'}
    public = {'status': 'failed', 'error_code': 'RESEARCH_INSUFFICIENT', 'result_ref': None}
    evidence = {'manifests': [], 'checkpoint': {'research_blocker': {'missing': ['SDK']}}, 'actions': [completion()]}
    assert_outcome(case, public, evidence)
    public['error_code'] = 'PROVIDER_UNAVAILABLE'
    with pytest.raises(AssertionError, match='WRONG_BUSINESS_FAILURE'):
        assert_outcome(case, public, evidence)


def test_secrets_are_redacted_without_erasing_usage():
    value = redact({'api_key': 'private', 'config_snapshot': {'provider': 'private'},
                    'usage': {'total_tokens': 42}, 'error': 'Bearer abc postgres://not-a-supported-url'})
    assert value['api_key'] == '[REDACTED]'
    assert value['usage']['total_tokens'] == 42
    assert 'Bearer abc' not in value['error']


def test_unsupported_scenario_writes_not_run_and_nonzero_exit(tmp_path):
    output = tmp_path/'result'
    code = main(['--env-file', str(tmp_path/'absent.env'), '--base-url', 'http://127.0.0.1:8027',
                 '--scenario', 'recovery', '--output-dir', str(output)])
    ledger = json.loads((output/'ledger.json').read_text())
    assert code == 2 and ledger['test_status'] == 'not_run' and ledger['runs'] == []
    assert 'SCENARIO_DRIVER_PENDING' in ledger['preflight_error']['reason']


def test_fixture_docx_is_real_zip_with_non_interview_topic():
    from scripts.verify_preparation_full_e2e import fixture_bytes
    from docx import Document
    import io
    document = Document(io.BytesIO(fixture_bytes('fractions')))
    text = '\n'.join(p.text for p in document.paragraphs)
    assert '1/2+1/3' in text and '面试' not in text
