from copy import deepcopy
import hashlib
import pytest
from app.exam_generation.validation import complete_result
from test_generation import repo, codec, create
from app.exam_generation.repository import GenerationConflict


def complete_paper():
    text = 'Reference paper'
    source_hash = hashlib.sha256(text.encode()).hexdigest()
    nodes, results = [], []
    for i in range(15):
        kind = 'choice' if i < 10 else 'fill_in_blank'
        node = {'question_id': f'q_{i}', 'question_type': kind, 'source_hash': source_hash,
                'option_keys': ['A', 'B', 'C', 'D', 'E'] if kind == 'choice' else [],
                'blank_count': 2 if kind == 'fill_in_blank' else 0, 'children': []}
        nodes.append(node)
        results.append({'qa_pair': {'question_id': f'q_{i}', 'question_type': kind,
            'question': f'Task {i}' if kind == 'choice' else f'Task {i}: ____ then ____',
            'correct_answer': 'E' if kind == 'choice' else '1,2', 'explanation': 'Proof',
            'options': {k: k+' answer' for k in node['option_keys']} or None,
            'blank_answers': ['1', '2'] if kind == 'fill_in_blank' else [], 'children': []},
            'metadata': {'blueprint_id': f'q_{i}', 'review_passed': True}})
    blueprint = {'version': 1, 'questions': nodes}
    return {'request': {'mode': 'mimic', 'num_questions': 5}, 'blueprint': deepcopy(blueprint),
        'parsed_sources': [{'role': 'template', 'content': text}],
        'result': {'metadata': {'summary': {'success': True, 'failed': 0, 'completed': 15,
            'template_count': 15, 'blueprint': blueprint, 'results': results}}}}


def test_fifteen_question_paper_must_match_independent_source_blueprint():
    row = complete_paper()
    assert complete_result(row)
    # Counts alone still match, but one source slot is repeated.
    results = row['result']['metadata']['summary']['results']
    results[-1] = deepcopy(results[-2])
    assert not complete_result(row)


def test_structure_only_result_needs_no_semantic_review_but_must_match_shape():
    row = complete_paper()
    results = row['result']['metadata']['summary']['results']
    for item in results:
        item['metadata'].pop('review_passed')
        item['metadata'].update(validation_mode='structure_only', structure_passed=True)
    assert complete_result(row)
    results[0]['qa_pair']['options'].pop('A')
    assert not complete_result(row)
    results[0]['qa_pair']['options']['A'] = 'Option A'
    results[0]['metadata']['structure_passed'] = False
    assert not complete_result(row)


def test_select_all_accepts_one_selected_key():
    from app.exam_generation.validation import _matches
    node = {'question_id': 'q', 'question_type': 'multiple_choice', 'option_keys': ['A', 'B']}
    question = {'question_id': 'q', 'question_type': 'multiple_choice', 'question': 'Select all',
                'options': {'A': 'One', 'B': 'Two'}, 'correct_answer': 'A',
                'correct_answers': ['A'], 'explanation': 'Explanation'}
    assert _matches(node, question)
    question['correct_answers'] = []
    assert not _matches(node, question)


@pytest.mark.parametrize('mutation', ['tail', 'order', 'option', 'blank', 'review', 'source', 'blueprint', 'absent_blueprint'])
def test_partial_or_self_reported_success_is_rejected(mutation):
    row = complete_paper()
    summary = row['result']['metadata']['summary']
    if mutation == 'tail':
        summary['results'].pop()
        summary['completed'] = summary['template_count'] = 14
    elif mutation == 'order': summary['results'].reverse()
    elif mutation == 'option': del summary['results'][0]['qa_pair']['options']['E']
    elif mutation == 'blank': summary['results'][-1]['qa_pair']['blank_answers'] = ['1']
    elif mutation == 'review': summary['results'][0]['metadata']['review_passed'] = False
    elif mutation == 'source': row['parsed_sources'][0]['content'] = 'Another paper'
    elif mutation == 'blueprint': summary['blueprint']['questions'].pop()
    else: del row['blueprint']
    assert not complete_result(row)


def test_blueprint_event_is_immutable_and_transactional(repo, codec):
    row = create(repo, codec)
    repo.claim('alice', row['id'], 1)
    event = {'seq': 1, 'type': 'progress', 'metadata': {'exam_blueprint': complete_paper()['blueprint']}}
    repo.event('alice', row['id'], 1, event)
    changed = deepcopy(event)
    changed['seq'] = 2
    changed['metadata']['exam_blueprint']['questions'].pop()
    with pytest.raises(GenerationConflict): repo.event('alice', row['id'], 1, changed)
    saved = repo.get('alice', row['id'])
    assert saved['last_seq'] == 1 and len(saved['blueprint']['questions']) == 15


def test_compound_children_and_multiple_answers_are_checked_independently():
    from app.exam_generation.validation import _matches
    node = {'question_id': 'parent', 'question_type': 'compound', 'children': [
        {'question_id': 'child', 'question_type': 'multiple_choice', 'option_keys': ['A', 'B', 'C'], 'children': []}]}
    candidate = {'question_id': 'parent', 'question_type': 'compound', 'question': 'Shared case',
        'correct_answer': 'A,C', 'explanation': 'Proof', 'children': [
            {'question_id': 'child', 'question_type': 'multiple_choice', 'question': 'Choose two',
             'correct_answer': 'A,C', 'correct_answers': ['A', 'C'], 'options': {'A': 'a', 'B': 'b', 'C': 'c'}, 'explanation': 'Proof'}]}
    assert _matches(node, candidate)
    candidate['children'][0]['correct_answers'] = ['A', 'Z']
    assert not _matches(node, candidate)
    candidate['children'][0]['correct_answers'] = ['A', 'C']
    candidate['children'][0]['question_id'] = 'different-child'
    assert not _matches(node, candidate)
