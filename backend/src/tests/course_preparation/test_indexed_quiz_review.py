import copy
import json
import pytest
from app.chat.harness.reviewed_resource import review_content
from app.chat.harness.preparation_content import preparation_metadata, value_digest
from app.course_preparation.generation_failures import GenerationFailure
from tests.course_preparation.test_generated_content_constraints import context, quiz_envelope, completion_review


def run_review(change=lambda response: None):
    envelope = quiz_envelope()
    body = envelope['content']
    metadata = preparation_metadata('quiz', body, envelope, context(), 'spec')
    before = copy.deepcopy(body)
    class Gateway:
        def chat(self, messages, **kwargs):
            request = json.loads(messages[-1]['content'])
            assert request['option_bindings'][0]['explanation_segments'] == [
                {'segment_index': 0, 'text': 'A 正确，程序执行。'},
                {'segment_index': 1, 'text': 'B 错误，模型只提出调用。'}]
            response = completion_review({'preparation': metadata}, 'quiz')
            response['preparation_checks'] = [{'binding_index': index, 'passed': check['passed'], 'reason': check['reason']}
                for index, check in enumerate(response['preparation_checks'])]
            for index, option in enumerate(response['question_checks'][0]['option_checks']):
                option.pop('explanation_excerpt')
                option['explanation_span'] = {'start_segment': index, 'end_segment': index}
            change(response)
            return json.dumps(response, ensure_ascii=False)
    result = review_content('quiz', body, {'preparation': metadata, 'teaching_context': context()}, Gateway(), durable=True)
    assert body == before and value_digest(body) == value_digest(before)
    return result


def test_indexed_quiz_review_restores_exact_original_excerpts():
    review, feedback = run_review()
    assert not feedback
    options = review.question_checks[0].option_checks
    assert [o.explanation_excerpt for o in options] == ['A 正确，程序执行。', 'B 错误，模型只提出调用。']
    assert all('explanation_span' not in o.model_dump() for o in options)


@pytest.mark.parametrize('span', [None, {'start_segment': 1, 'end_segment': 0},
    {'start_segment': 0, 'end_segment': 20}, {'start_segment': True, 'end_segment': 1}])
def test_invalid_excerpt_selection_cannot_be_accepted(span):
    def change(response): response['question_checks'][0]['option_checks'][0]['explanation_span'] = span
    with pytest.raises(GenerationFailure, match='RESOURCE_REVIEW_RESPONSE_INVALID'): run_review(change)


def test_missing_explanation_is_rejected_content_not_invented_quote():
    def change(response):
        response['question_checks'][0]['option_checks'][0].update(explanation_span=None, explanation_valid=False)
    review, feedback = run_review(change)
    assert review.question_checks[0].option_checks[0].explanation_excerpt == ''
    assert feedback


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'unknown', 'rejected'])
def test_indexed_bindings_keep_full_coverage_and_semantic_rejection(fault):
    def change(response):
        checks=response['preparation_checks']
        if fault=='duplicate':checks[1]['binding_index']=checks[0]['binding_index']
        elif fault=='missing':checks.pop()
        elif fault=='unknown':checks[0]['binding_index']=999
        else:checks[0]['passed']=False
    if fault=='rejected':
        _,feedback=run_review(change)
        assert feedback
    else:
        with pytest.raises(GenerationFailure,match='RESOURCE_REVIEW_RESPONSE_INVALID'):run_review(change)
