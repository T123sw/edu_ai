import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.chat.harness.quiz_policy import planned_metadata, structure_receipt, validate_submission
from app.chat.harness.reviewed_resource import ReviewedResourceGenerator, verified_resource
from app.course_preparation.resource_alignment import validate_artifact, resource_checks
from app.course_preparation.quality import candidate_manifest
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.tool_registry import digest


def body():
    return {'title': '位置编码', 'questions': [
        {'id': 'q1', 'type': 'short_answer', 'stem': '写出位置编码的符号形式。',
         'answer': 'sin(pos), cos(pos)', 'explanation': 'pos 为位置变量。'},
        {'id': 'q2', 'type': 'single_choice', 'stem': '哪个是位置变量？',
         'options': ['pos', '常数 1'], 'answer': 'A', 'explanation': 'A 是变量，B 是常数。'}]}


class Writer:
    def __init__(self):
        self.calls = 0
        self.schema = None

    def with_response_schema(self, schema, validator):
        self.schema, self.validator = schema, validator
        return self

    def chat(self, messages, **kwargs):
        self.calls += 1
        assert self.schema['required'] == ['content']
        self.validator({'content': body()})
        return json.dumps({'content': body()})


class NoReview:
    def chat(self, *args, **kwargs):
        pytest.fail('Quiz generation must not call a reviewer')


def test_quiz_uses_one_typed_submission_and_no_model_or_numeric_review(monkeypatch):
    import app.chat.harness.reviewed_resource as module
    monkeypatch.setattr(module, 'review_content', lambda *a, **k: pytest.fail('unexpected review'))
    monkeypatch.setattr(module, 'verify_calculations', lambda *a, **k: pytest.fail('unexpected numeric review'))
    writer = Writer()
    result = ReviewedResourceGenerator(writer, review_gateway=NoReview()).generate(
        SimpleNamespace(resource_type='quiz', title='位置编码'), job_id='j', config_snapshot_id='c')
    artifact = result['artifacts'][0]
    assert writer.calls == 1 and artifact['content'] == body()
    from app.self_learning.check_service import CheckService
    questions = [CheckService.bank_question(q) for q in artifact['content']['questions']]
    assert [q.form for q in questions] == ['short_answer', 'choice']
    assert questions[1].correct_option_ids == ['option_1']
    assert verified_resource(artifact, 'quiz')
    receipt = artifact['generation_state']['resource_review']
    assert receipt['decision'] == 'skipped' and receipt['method'] == 'structural_validation'
    artifact['content']['questions'][0]['answer'] = 'changed'
    assert not verified_resource(artifact, 'quiz')


@pytest.mark.parametrize('mutation', ['empty', 'duplicate', 'answer', 'stem', 'missing', 'extra'])
def test_invalid_display_structure_cannot_be_delivered(mutation):
    content = body()
    if mutation == 'empty':
        content['questions'] = []
    elif mutation == 'duplicate':
        content['questions'][1]['id'] = 'q1'
    elif mutation == 'answer':
        content['questions'][1]['answer'] = 'Z'
    elif mutation == 'stem':
        content['questions'][0]['stem'] = {'text': 'not a string'}
    elif mutation == 'missing':
        del content['questions'][0]['explanation']
    else:
        content['review'] = 'pass'
    with pytest.raises(Exception):
        validate_submission({'content': content})


def test_interrupted_candidate_finishes_without_resuming_old_review(monkeypatch):
    import app.chat.harness.quiz_policy as module
    monkeypatch.setattr(module, 'phase_gateway', lambda *a: pytest.fail('must reuse valid candidate'))
    saved = []
    checkpoint = SimpleNamespace(
        load_review_candidate=lambda: {'spec_digest': 'spec', 'content_digest': digest(body()),
            'content': body(), 'review_state': {'needs_repair': True, 'feedback': ['old semantic audit']}},
        save_review_candidate=lambda **kwargs: saved.append(kwargs))
    result = ReviewedResourceGenerator(NoReview(), checkpoint=checkpoint).generate(
        SimpleNamespace(resource_type='quiz', title='位置编码', spec_digest='spec'), job_id='j', config_snapshot_id='c')
    assert verified_resource(result['artifacts'][0], 'quiz')
    assert saved[0]['review_state']['history'] == []
    assert saved[0]['review_state']['needs_repair'] is False


def test_explicit_revision_supplies_original_content_to_single_write():
    class RevisionWriter(Writer):
        def chat(self, messages, **kwargs):
            spec = json.loads(messages[-1]['content'])['specification']
            assert spec['original_content'] == body()
            assert spec['revision_feedback'] == ['澄清第二题题干']
            return super().chat(messages, **kwargs)

    writer = RevisionWriter()
    ReviewedResourceGenerator(writer, review_gateway=NoReview()).generate(
        SimpleNamespace(resource_type='quiz', title='位置编码', original_content=body(),
                        revision_feedback=['澄清第二题题干']), job_id='j', config_snapshot_id='c')
    assert writer.calls == 1


def test_structural_quiz_is_ready_without_fabricated_per_question_coverage():
    from tests.course_preparation.test_resource_alignment import quiz, checkpoint
    artifact = quiz()
    metadata = planned_metadata(artifact['spec']['teaching_context'], artifact['spec_digest'])
    artifact['content'] = {'content': body(), 'generation_state': {
        'preparation': metadata, 'resource_review': structure_receipt(body(), metadata)}}
    artifact['content_digest'] = digest(artifact['content'])
    validate_artifact(artifact)
    assert verified_resource(artifact['content'], 'quiz')
    assert resource_checks(artifact, 'n') == []
    result = candidate_manifest(SimpleNamespace(preparation_id='prep', owner_user_id='alice'),
        checkpoint(artifact), PreparationRequest(request_id=uuid4(), operation='create_course', goal='学习加法'))
    assert result.nodes[0].resources[0].objective_coverage == 'planned'
    changed = copy.deepcopy(artifact['content'])
    changed['generation_state']['preparation']['spec_digest'] = 'changed'
    assert not verified_resource(changed, 'quiz')
