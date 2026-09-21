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


def test_canceled_model_scenario_requires_settlement_and_no_delivery():
    case = {'expected_business_status': 'canceled'}
    public = {'status': 'canceled', 'result_ref': None, 'budget': {'reserved': {'calls': 0, 'tokens': 0}}}
    action = {**completion(), 'action_id': 'inflight'}
    evidence = {'manifests': [], 'actions': [action], 'canceled_model_action_id': 'inflight'}
    assert_outcome(case, public, evidence)
    public['budget']['reserved']['tokens'] = 100
    with pytest.raises(AssertionError, match='CANCELED_BUDGET_NOT_SETTLED'):
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


def test_cost_summary_counts_provider_failures_and_sources_separately():
    from scripts.verify_preparation_full_e2e import action_summary
    failed = completion(); failed['status'] = 'failed'
    summary = action_summary([completion(), failed, {'kind': 'source_read', 'status': 'completed'}])
    assert summary['model_attempts'] == 2 and summary['model_completions'] == 1
    assert summary['failed_model_attempts'] == 1 and summary['source_actions'] == 1
    assert summary['phases']['resource_review'] == {'completed': 1, 'failed': 1, 'pending': 0}


def test_parameter_ledger_does_not_turn_prompt_presence_into_semantic_success():
    from scripts.verify_preparation_full_e2e import parameter_ledger
    rows = parameter_ledger({'artifacts': [{'artifact_id': 'a', 'resource_id': 'r', 'resource_version': 1,
        'resource_type': 'report', 'spec_digest': 'a'*64, 'content_digest': 'b'*64,
        'spec': {'teaching_context': {'language': 'zh-CN'}}, 'content': {}}]})
    language = next(r for r in rows[0]['rows'] if r['input_path'] == 'teaching_context.language')
    assert language['validated_value'] == 'zh-CN' and language['artifact_locator'] is None
    assert language['check_result'] == 'payload_present_effect_requires_semantic_review'


def test_upload_only_case_rejects_any_network_attempt_even_failed():
    case = {'expected_business_status': 'failed', 'expected_error_code': 'RESEARCH_INSUFFICIENT', 'source_mode': 'uploaded_only'}
    public = {'status': 'failed', 'error_code': 'RESEARCH_INSUFFICIENT'}
    evidence = {'actions': [completion(), {'kind': 'search', 'status': 'failed'}]}
    with pytest.raises(AssertionError, match='UPLOADED_ONLY_USED_NETWORK'):
        assert_outcome(case, public, evidence)


def test_learning_readback_checks_body_not_only_version_label():
    from scripts.verify_preparation_full_e2e import assert_material_readback
    from app.course_preparation.tool_registry import digest
    original = {'content': '# First example\n12 + 30 = 42'}
    resource = {'version': 2, 'resource_type': 'report', 'content_sha256': digest(original)}
    material = {'version': 2, 'visibility': 'private', 'content_hash': digest(original),
                'preparation_artifact': original, 'content': original['content']}
    assert_material_readback(material, resource)
    material['content'] = 'silently substituted body'
    with pytest.raises(AssertionError, match='LEARNING_BODY_PROJECTION_MISMATCH'):
        assert_material_readback(material, resource)


# Reuse actual SQL artifacts/parent leases and queue fixtures; only the final
# generator body is intercepted. This is wiring evidence, never live content QA.
from tests.course_preparation.test_generation_adapter import generation


@pytest.mark.parametrize('kind', ['report', 'quiz', 'classroom'])
def test_registered_resource_handler_delivers_a_context_and_f_checkpoint_to_generators(generation, monkeypatch, kind):
    from app.course_preparation.harness_generation import PreparationHarnessGateway
    from app.course_preparation.generation_failures import GenerationFailure, FailureDetail
    from types import SimpleNamespace
    from app.course_preparation.adapters.generation import PreparationResourceHandler
    from app.course_preparation.runtime_contracts import BudgetCost
    from app.course_preparation.tool_registry import digest
    from tests.course_preparation.test_spec_compatibility import v2_spec
    from app.course_preparation import research_dependencies
    from app.chat.harness import reviewed_report, reviewed_resource
    from app.course_preparation.adapters import classroom

    repo, parent, adapter = generation
    value = {**v2_spec(), 'resource_type': kind, 'memory_subject': 'alice', 'memory_refs': {}, 'memory_epoch': 0}
    action = repo.begin_action(parent, 'g-wiring-' + kind, 'generate_resource', value, BudgetCost(calls=1))
    receipt = adapter.submit(parent, value, action['action_id'])
    configured = SimpleNamespace(candidates=[{'model_name': 'contract-only'}])
    monkeypatch.setattr(research_dependencies, 'agent_factory', lambda *args: SimpleNamespace(model=SimpleNamespace(gateway=configured)))
    checked = []

    def inspect_input(payload, gateway, checkpoint):
        assert gateway.preparation_harness is True
        assert payload.teaching_context == value['teaching_context']
        assert payload.resource_target_minutes is None
        assert not getattr(payload, 'harness_chapters', None)
        assert checkpoint is not None, 'F_CHECKPOINT_NOT_WIRED'
        checkpoint.save_review_candidate(content='private candidate', content_digest=digest('private candidate'),
            spec_digest=digest(value), review_state={'phase': 'resource_review'})
        assert checkpoint.load_review_candidate()['content'] == 'private candidate'
        checked.append(kind)
        # Stop at the real generator boundary with a typed review failure.
        # This tests wiring and persistence without inventing reviewed content.
        raise GenerationFailure(FailureDetail(code='TEST_REVIEW_FORMAT', phase='resource_review',
            category='review_format', retry_scope='review', message='injected review format failure',
            content_digest=digest('private candidate')))

    def report(payload, *, gateway, checkpoint=None, **kwargs):
        inspect_input(payload, gateway, checkpoint)
        return 'contract-only body', {}

    def room(payload, *, gateway, checkpoint=None, **kwargs):
        inspect_input(payload, gateway, checkpoint)
        return {'artifact_type': 'classroom', 'content': {'scenes': []}}

    class Quiz:
        def __init__(self, *, gateway, checkpoint=None, **kwargs):
            self.gateway, self.checkpoint = gateway, checkpoint
        def generate(self, payload, **kwargs):
            inspect_input(payload, self.gateway, self.checkpoint)
            return {'artifacts': [{'artifact_type': 'quiz', 'content': {'questions': []}}]}

    monkeypatch.setattr(reviewed_report, 'generate_reviewed_report', report)
    monkeypatch.setattr(reviewed_resource, 'ReviewedResourceGenerator', Quiz)
    monkeypatch.setattr(classroom, 'generate_classroom_draft', room)
    context = SimpleNamespace(owner_user_id='alice', task_id=receipt['job_id'],
                              is_cancel_requested=lambda: False, progress=lambda *a, **kw: None)
    with pytest.raises(GenerationFailure, match='TEST_REVIEW_FORMAT'):
        PreparationResourceHandler(lambda: SimpleNamespace(repository=repo))({'artifact_id': receipt['artifact_id']}, context)
    failed=adapter.artifacts.get('alice',receipt['artifact_id'],content=True)
    assert checked == [kind] and failed['status']=='failed'
    assert failed['failure_detail']['retry_scope']=='review'
    assert failed['content']['_review_candidate']['content']=='private candidate'
