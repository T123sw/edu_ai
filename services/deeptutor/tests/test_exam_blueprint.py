import json
import re
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from deeptutor.agents.question import mimic_source
from deeptutor.agents.question.pipeline import QuestionPipeline, QuizTemplate, QuizPlan, QuizPair
from deeptutor.core.context import UnifiedContext, Attachment
from deeptutor.runtime.agentic import LabeledStepResult
from deeptutor.runtime.stream_bus import StreamBus
from deeptutor.services.llm.config import LLMConfig
from deeptutor.tools.question import question_extractor as extractor
from edu_deeptutor.runtime import QuestionCheckpoint


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr('deeptutor.agents.question.pipeline.get_llm_config', lambda: LLMConfig(model='offline', api_key='fake'))
    instance = QuestionPipeline(language='en')
    monkeypatch.setattr(instance, '_prepare_pageindex_tools', AsyncMock())
    monkeypatch.setattr('deeptutor.agents.question.pipeline.build_openai_client', lambda _: object())
    monkeypatch.setattr(instance, '_tool_list_text', lambda _: '- none')
    monkeypatch.setattr(instance, '_use_native_tools', lambda _: False)
    return instance


def template(kind='short_answer', **extra):
    node = mimic_source._blueprint_question({'question_text': 'Explain pivot partition in quicksort.', 'question_type': kind,
        'concept': 'Quicksort pivot partition', **extra}, 1, 'a' * 64)
    return QuizTemplate(node['question_id'], node['concept'], kind, 'medium', source='mimic',
        reference_question=node['reference_question'], blueprint=node)


def test_unknown_types_and_missing_asset_fail_instead_of_changing_paper(tmp_path):
    with pytest.raises(ValueError, match='Unsupported'): mimic_source._coerce_question_type('unrecognized')
    (tmp_path / 'exam.md').write_text('Question with figure')
    (tmp_path / 'exam_questions.json').write_text(json.dumps({'questions': [
        {'question_text': 'Read the graph', 'question_type': 'short_answer', 'images': ['missing.png']}]}))
    with pytest.raises(ValueError, match='unavailable image'):
        mimic_source._parse_sync(tmp_path, 0, 'parsed', tmp_path / 'out')


def test_source_blueprint_retains_sections_repeated_numbers_children_and_assets(tmp_path):
    (tmp_path / 'images').mkdir()
    (tmp_path / 'images/figure.png').write_bytes(b'fixture-image')
    (tmp_path / 'exam.md').write_text('Complete source')
    questions = [
        {'question_number': '1', 'section': 'I', 'question_text': 'Select all A. a B. b C. c E. e', 'question_type': 'multiple_choice', 'option_keys': ['A', 'B', 'C', 'E'], 'images': ['figure.png']},
        {'question_number': '1', 'section': 'II', 'question_text': 'Values ____ and ____', 'question_type': 'fill_in_blank', 'blank_count': 2},
        {'question_number': '2', 'section': 'II', 'question_text': 'Shared case', 'question_type': 'compound', 'children': [
            {'question_text': 'First calculation', 'question_type': 'short_answer'},
            {'question_text': 'Second calculation', 'question_type': 'coding'}]}]
    (tmp_path / 'exam_questions.json').write_text(json.dumps({'questions': questions}))
    one, trace = mimic_source._parse_sync(tmp_path, 0, 'parsed', tmp_path / 'out')
    two, _ = mimic_source._parse_sync(tmp_path, 0, 'parsed', tmp_path / 'out')
    assert [t.question_id for t in one] == [t.question_id for t in two]
    assert len(set(t.question_id for t in one)) == 3
    assert one[0].blueprint['option_keys'] == ['A', 'B', 'C', 'E']
    assert one[0].source_images[0].base64
    assert one[1].blueprint['blank_count'] == 2
    assert len(one[2].blueprint['children']) == 2
    frozen = json.loads(Path(trace['blueprint_file']).read_text())
    assert frozen['questions'] == [t.blueprint for t in one]


def test_extended_shapes_reject_missing_options_blanks_and_children(pipeline):
    multi = template('multiple_choice', option_keys=['A', 'B', 'C', 'D', 'E'])
    payload = {'question': 'New question', 'correct_answer': 'A,E', 'correct_answers': ['A', 'E'],
        'options': {key: key + ' value' for key in ['A', 'B', 'C', 'D', 'E']}, 'explanation': 'Proof'}
    normalized = pipeline._normalize_quiz_payload(multi, payload)
    assert not pipeline._collect_quiz_issues(multi, normalized)
    assert 'E' in normalized['options']
    normalized['correct_answers'] = ['A']
    normalized['correct_answer'] = 'A'
    assert not pipeline._collect_quiz_issues(multi, normalized)
    normalized['correct_answers'] = []
    assert 'multiple_choice_answers_invalid' in pipeline._collect_quiz_issues(multi, normalized)
    blanks = template('fill_in_blank', blank_count=2)
    value = pipeline._normalize_quiz_payload(blanks, {'question': '____ and ____', 'correct_answer': '1,2', 'blank_answers': ['1', '2'], 'explanation': 'two values'})
    assert not pipeline._collect_quiz_issues(blanks, value)
    six = pipeline._normalize_quiz_payload(blanks, {**value, 'question': '______ and ______'})
    assert six['question'] == '____ and ____' and not pipeline._collect_quiz_issues(blanks, six)
    value['question'] = 'Only ____'
    assert 'blank_count_mismatch' in pipeline._collect_quiz_issues(blanks, value)
    compound = template('compound', children=[{'question_text': 'Child', 'question_type': 'short_answer'}])
    value = pipeline._normalize_quiz_payload(compound, {'question': 'Parent', 'correct_answer': 'Answer', 'explanation': 'Proof'})
    assert 'subquestion_count_mismatch' in pipeline._collect_quiz_issues(compound, value)
    node = compound.blueprint['children'][0]
    value['children'] = [{'question_id': node['question_id'], 'question_type': 'short_answer', 'question': 'Child task', 'correct_answer': 'Result', 'explanation': 'Proof'}]
    assert not pipeline._collect_quiz_issues(compound, value)
    forged = pipeline._normalize_quiz_payload(compound, {**value, 'children': [{**value['children'][0], 'question_type': 'coding'}]})
    assert any('question_type_mismatch' in issue for issue in pipeline._collect_quiz_issues(compound, forged))


@pytest.mark.asyncio
async def test_generation_accepts_structure_without_independent_review(pipeline, monkeypatch):
    item = template()
    payload = {'question': 'Which node is the root?', 'correct_answer': 'A', 'explanation': 'A is the root.'}
    generate = AsyncMock(return_value=SimpleNamespace(final_text=json.dumps(payload)))
    monkeypatch.setattr('deeptutor.agents.question.pipeline.run_agentic_loop', generate)
    review = AsyncMock(side_effect=AssertionError('Content review must not run'))
    monkeypatch.setattr(pipeline, '_review_mimic', review)
    monkeypatch.setattr(pipeline, '_run_labeled_step', review)
    pair = await pipeline._quiz_one(template=item, question_number=1, total_questions=1, exploration_trace='',
        plan=QuizPlan('', [item]), previous_pairs=[], image_attachments=[],
        context=UnifiedContext(user_message='Use the same topic'), stream=StreamBus(), client=object())
    assert generate.await_count == 1 and review.await_count == 0
    assert pair.correct_answer == 'A' and pair.metadata['structure_passed']
    assert pair.metadata['validation_mode'] == 'structure_only' and 'review_passed' not in pair.metadata


@pytest.mark.asyncio
async def test_missing_structure_gets_only_two_bounded_repairs(pipeline, monkeypatch):
    item = template()
    payload = {'question': 'Question missing its answer', 'explanation': 'Explanation'}
    monkeypatch.setattr('deeptutor.agents.question.pipeline.run_agentic_loop', AsyncMock(return_value=SimpleNamespace(final_text=json.dumps(payload))))
    repair = AsyncMock(return_value=payload)
    monkeypatch.setattr(pipeline, '_repair_quiz_payload', repair)
    review = AsyncMock(side_effect=AssertionError('Content review must not run'))
    monkeypatch.setattr(pipeline, '_review_mimic', review)
    pair = await pipeline._quiz_one(template=item, question_number=1, total_questions=1, exploration_trace='',
        plan=QuizPlan('', [item]), previous_pairs=[], image_attachments=[], context=UnifiedContext(), stream=StreamBus(), client=object())
    assert repair.await_count == 2 and review.await_count == 0
    assert pair.metadata['structure_passed'] is False
    assert pair.metadata['issues'] == ['missing_correct_answer']


@pytest.mark.asyncio
async def test_structural_repair_finishes_without_followup_review(pipeline, monkeypatch):
    item = template('choice', option_keys=['A', 'B', 'C', 'D'])
    initial = {'question': 'Which statement is false?', 'correct_answer': 'D', 'explanation': 'D is false.'}
    fixed = {**initial, 'options': {'A': 'Numeric fact', 'B': 'Numeric fact', 'C': 'Numeric fact', 'D': 'Conceptual claim'}}
    monkeypatch.setattr('deeptutor.agents.question.pipeline.run_agentic_loop', AsyncMock(return_value=SimpleNamespace(final_text=json.dumps(initial))))
    repair = AsyncMock(return_value=fixed)
    monkeypatch.setattr(pipeline, '_repair_quiz_payload', repair)
    review = AsyncMock(side_effect=AssertionError('Content review must not run'))
    monkeypatch.setattr(pipeline, '_review_mimic', review)
    pair = await pipeline._quiz_one(template=item, question_number=1, total_questions=1, exploration_trace='',
        plan=QuizPlan('', [item]), previous_pairs=[], image_attachments=[], context=UnifiedContext(), stream=StreamBus(), client=object())
    assert repair.await_count == 1 and review.await_count == 0
    assert pair.metadata['structure_passed'] and pair.options == fixed['options']


@pytest.mark.asyncio
async def test_partial_generation_resumes_successful_prefix_only(pipeline, monkeypatch, tmp_path):
    monkeypatch.setenv('DEEPTUTOR_HOME', str(tmp_path))
    items = [template(), template(question_text='Second quicksort task')]
    # Stable but distinct source ordinals.
    node = mimic_source._blueprint_question({'question_text': 'Second quicksort task', 'question_type': 'short_answer'}, 2, 'a' * 64)
    items[1] = QuizTemplate(node['question_id'], node['concept'], 'short_answer', 'medium', source='mimic', blueprint=node)
    store = QuestionCheckpoint('alice', 'request', {'model': 'v1'})
    calls = []
    fail = True
    async def generate(**kwargs):
        item = kwargs['template']
        calls.append(item.question_id)
        if fail and len(calls) == 2:
            raise RuntimeError('Interrupted after one success')
        return QuizPair(item.question_id, 'New task '+item.question_id, 'short_answer', 'Answer', 'Proof', metadata={'review_passed': True, 'blueprint_id': item.question_id})
    monkeypatch.setattr(pipeline, '_quiz_one', generate)
    ctx = UnifiedContext(user_message='Generate')
    ctx.extension('question_pipeline')['checkpoint'] = store
    kwargs = dict(context=ctx, user_message='Generate', num_questions=2, templates_override=items, stream=StreamBus())
    with pytest.raises(RuntimeError): await pipeline.run(**kwargs)
    fail = False
    result = await pipeline.run(**{**kwargs, 'stream': StreamBus()})
    assert calls == [items[0].question_id, items[1].question_id, items[1].question_id]
    assert result['summary']['completed'] == 2
    assert QuestionCheckpoint('bob', 'request', {'model': 'v1'}).read(items[0], []) is None
    assert QuestionCheckpoint('alice', 'request', {'model': 'v2'}).read(items[0], []) is None
    assert QuestionCheckpoint('alice', 'fresh-request', {'model': 'v1'}).read(items[0], []) is None


def test_bad_source_spans_receive_one_bounded_extraction_repair(monkeypatch, tmp_path):
    calls = []
    def window(text, *args):
        calls.append(text)
        question = {'question_text': 'Question', 'question_type': 'short_answer'}
        if len(calls) == 2:
            question.update(source_start_line=1, source_end_line=1)
        return {'questions': [question], 'incomplete_questions': []}
    monkeypatch.setattr(extractor, '_extract_question_window', window)
    found = extractor.extract_questions_with_llm('Question', [], tmp_path, 'fake', 'https://invalid', 'fake')
    assert len(calls) == 2 and 'EXTRACTION CORRECTION' in calls[1]
    assert found[0]['source_text'] == 'Question'


def test_empty_extracted_question_cannot_disappear_from_the_blueprint(tmp_path):
    (tmp_path / 'exam_questions.json').write_text(json.dumps({'questions': [
        {'question_text': 'Valid', 'question_type': 'short_answer'},
        {'question_text': '', 'question_type': 'written'}]}))
    with pytest.raises(ValueError, match='missing or invalid'):
        mimic_source._parse_sync(tmp_path, 0, 'parsed', tmp_path / 'out')


def test_checkpoint_revision_change_invalidates_old_reviews(monkeypatch, tmp_path):
    monkeypatch.setenv('DEEPTUTOR_HOME', str(tmp_path))
    monkeypatch.setattr('edu_deeptutor.runtime._migration_revision', lambda: 'old-reviewed-pipeline')
    item = template()
    store = QuestionCheckpoint('alice', 'request', {'model': 'same'})
    store.save(item, [], {'old': True})
    assert store.read(item, []) == {'old': True}
    monkeypatch.setattr('edu_deeptutor.runtime._migration_revision', lambda: 'new-reviewed-pipeline')
    assert QuestionCheckpoint('alice', 'request', {'model': 'same'}).read(item, []) is None


@pytest.mark.asyncio
async def test_retry_reuses_successful_later_slots_and_passes_them_as_avoidance(pipeline, monkeypatch, tmp_path):
    monkeypatch.setenv('DEEPTUTOR_HOME', str(tmp_path))
    items = []
    for i in (1, 2):
        node = mimic_source._blueprint_question({'question_text': f'Source {i}', 'question_type': 'short_answer'}, i, 'a' * 64)
        items.append(QuizTemplate(node['question_id'], node['concept'], 'short_answer', 'medium', source='mimic', blueprint=node))
    context = UnifiedContext(user_message='New tasks')
    context.extension('question_pipeline')['checkpoint'] = QuestionCheckpoint('alice', 'same-request', {'model': 'same'})
    calls = []
    async def generate(**kwargs):
        item = kwargs['template']
        calls.append((item.question_id, [p.question_id for p in kwargs['previous_pairs']]))
        issues = ['answer_invalid'] if len(calls) == 1 else []
        return QuizPair(item.question_id, 'New task '+item.question_id, 'short_answer', 'Answer', 'Proof',
            metadata={'issues': issues, 'review_passed': not issues, 'blueprint_id': item.question_id})
    monkeypatch.setattr(pipeline, '_quiz_one', generate)
    for _ in range(2):
        result = await pipeline.run(context=context, user_message='New tasks', num_questions=2, templates_override=items, stream=StreamBus())
    assert result['summary']['completed'] == 2
    assert [i for i, _ in calls] == [items[0].question_id, items[1].question_id, items[0].question_id]
    assert calls[-1][1] == [items[1].question_id]


def test_child_ids_are_assigned_by_frozen_order_not_model_text(pipeline):
    item=template('compound',children=[{'question_text':'Task','question_type':'coding'}])
    result=pipeline._normalize_quiz_payload(item,{'question':'Parent','correct_answer':'A','explanation':'Proof','children':[
        {'question_id':'invented-id','question_type':'coding','question':'Implement','correct_answer':'return 1','explanation':'Proof'}]})
    assert result['children'][0]['question_id']==item.blueprint['children'][0]['question_id']
    assert result['question_id']==item.question_id


@pytest.mark.asyncio
async def test_text_review_uses_frozen_provider_without_mutating_visual_pipeline(pipeline, monkeypatch):
    pipeline.llm_config.edu_text_model = {'model': 'text-review', 'binding': 'deepseek',
        'base_url': 'http://127.0.0.1:1/v1', 'api_key': 'private-review', 'reasoning_effort': 'none'}
    original = (pipeline.model, pipeline.binding, pipeline.client_config)
    seen = []
    async def checked(self, template, payload, requirements, stream, client, previous, images=None):
        seen.append((self.model, list(images or template.source_images)))
        return []
    monkeypatch.setattr(QuestionPipeline, '_review_mimic_checked', checked)
    t = template()
    await pipeline._review_mimic(t, {}, '', StreamBus(), object(), [])
    t.source_images.append(Attachment(type='image', filename='figure.png', base64='eA==', mime_type='image/png'))
    await pipeline._review_mimic(t, {}, '', StreamBus(), object(), [])
    assert seen[0] == ('text-review', [])
    assert seen[1][0] == original[0] and seen[1][1] == t.source_images
    assert (pipeline.model, pipeline.binding, pipeline.client_config) == original


@pytest.mark.asyncio
async def test_text_question_generation_uses_text_provider_and_visual_keeps_images(pipeline, monkeypatch):
    pipeline.llm_config.edu_text_model = {'model':'text-review','binding':'deepseek',
        'base_url':'http://127.0.0.1:1/v1','api_key':'private-review','reasoning_effort':'none'}
    original_model = pipeline.model
    seen = []
    async def generate(**kwargs):
        seen.append((kwargs['model'],json.dumps(kwargs['initial_messages'])))
        return SimpleNamespace(final_text=json.dumps({'question':'Partition [3,1,4] using 3.',
            'correct_answer':'[1],3,[4]','explanation':'1<3<4'}))
    monkeypatch.setattr('deeptutor.agents.question.pipeline.run_agentic_loop', generate)
    monkeypatch.setattr(QuestionPipeline, '_review_mimic', AsyncMock(return_value=[]))
    t = template()
    args = dict(template=t,question_number=1,total_questions=1,exploration_trace='',
        plan=QuizPlan('',[t]),previous_pairs=[],context=UnifiedContext(),stream=StreamBus(),client=object())
    await pipeline._quiz_one(**args,image_attachments=[])
    await pipeline._quiz_one(**args,image_attachments=[Attachment(type='image',filename='context.png',mime_type='image/png',base64='ZmlndXJl')])
    assert seen[0][0] == 'text-review' and seen[1][0] == original_model
    assert 'ZmlndXJl' not in seen[0][1] and 'ZmlndXJl' in seen[1][1]
    assert pipeline.model == original_model


@pytest.mark.asyncio
async def test_bad_independent_proof_gets_one_repair_without_rewriting_correct_question(pipeline, monkeypatch):
    q = {'question_type':'choice','question':'Compute 1+1','options':{'A':'2','B':'3'},
         'correct_answer':'A','explanation':'SECRET_AUTHOR: two units.'}
    calls = []
    async def step(**kwargs):
        calls.append(kwargs['messages'])
        if len(calls) < 3:
            data = {'well_posed':True,'requires_computation':True,'solution':'2',
                'calculations':[{'expression':'1+1','expected':3 if len(calls)==1 else 2}],
                'option_checks':{'A':'1+1==2','B':'1+1==3'}}
        else:
            data = dict(concept_match=True,novel_question=True,answer_valid=True,requirements_met=True,
                same_task_rephrased=False,task_change_evidence='New input',independent_solution='2',issues=[])
        return LabeledStepResult(label='FINISH',text=json.dumps(data))
    monkeypatch.setattr(pipeline,'_run_labeled_step',step)
    assert await pipeline._review_mimic(template(),q,'',StreamBus(),object(),[]) == []
    assert len(calls)==3
    assert 'calculator_feedback' in json.dumps(calls[1])
    assert 'SECRET_AUTHOR' not in json.dumps(calls[:2]) and 'SECRET_AUTHOR' in json.dumps(calls[2])


@pytest.mark.asyncio
async def test_non_unique_computed_choice_never_reaches_accepting_reviewer(pipeline, monkeypatch):
    q = {'question_type':'choice','question':'Which number is even?',
         'options':{'A':'2','B':'4'},'correct_answer':'A','explanation':'Two is even.'}
    step=AsyncMock(return_value=LabeledStepResult(label='FINISH',text=json.dumps({
        'well_posed':True,'requires_computation':True,'solution':'A',
        'calculations':[{'expression':'2%2','expected':0}],
        'option_checks':{'A':'2%2==0','B':'4%2==0'}})))
    monkeypatch.setattr(pipeline,'_run_labeled_step',step)
    issues=await pipeline._review_mimic(template(),q,'',StreamBus(),object(),[])
    assert any('single_choice_not_unique' in issue for issue in issues)
    assert step.await_count == 2  # Blind solve and bounded proof repair; no accepting comparison.


@pytest.mark.asyncio
async def test_solver_rechecks_claimed_ambiguity_without_author_answer(pipeline,monkeypatch):
    q={'question_type':'short_answer','question':'For i,j in 0..4 list positions with 4-i<=j<=5-i.',
        'correct_answer':'PRIVATE_AUTHOR','explanation':'PRIVATE_EXPLANATION'}
    responses=[{'well_posed':False,'requires_computation':True,'solution':'I assumed every row needs two items.',
        'calculations':[{'expression':'len([[i,j] for i in range(5) for j in range(5) if 4-i<=j<=5-i])','expected':9}]},
        {'well_posed':True,'requires_computation':True,'solution':'Explicit bounds exclude (0,5); nine entries.',
        'calculations':[{'expression':'len([[i,j] for i in range(5) for j in range(5) if 4-i<=j<=5-i])','expected':9}]},
        dict(concept_match=True,novel_question=True,answer_valid=True,requirements_met=True,
             same_task_rephrased=False,task_change_evidence='New bounded matrix',independent_solution='Nine entries')]
    calls=[]
    async def step(**kwargs):
        calls.append(kwargs['messages']);return LabeledStepResult(label='FINISH',text=json.dumps(responses[len(calls)-1]))
    monkeypatch.setattr(pipeline,'_run_labeled_step',step)
    assert await pipeline._review_mimic(template(),q,'',StreamBus(),object(),[])==[]
    assert len(calls)==3 and 'PRIVATE_' not in json.dumps(calls[:2])


@pytest.mark.asyncio
async def test_numerically_wrong_reviewer_is_checked_before_rewriting_correct_question(pipeline,monkeypatch):
    q={'question_type':'short_answer','question':'Compute 19+6.','correct_answer':'25','explanation':'Nineteen plus six is twenty-five.'}
    valid=dict(concept_match=True,novel_question=True,answer_valid=True,requirements_met=True,
        same_task_rephrased=False,task_change_evidence='New operands',independent_solution='25')
    responses=[{'well_posed':True,'requires_computation':True,'solution':'25','calculations':[{'expression':'19+6','expected':25}]},
        {**valid,'answer_valid':False,'independent_solution':'27','issues':['The answer must be 27.'],
            'calculations':[{'expression':'19+6','expected':27}]},valid]
    calls=[]
    async def step(**kwargs):
        calls.append(kwargs['messages']);return LabeledStepResult(label='FINISH',text=json.dumps(responses[len(calls)-1]))
    monkeypatch.setattr(pipeline,'_run_labeled_step',step)
    assert await pipeline._review_mimic(template(),q,'',StreamBus(),object(),[])==[]
    assert 'calculation_mismatch' in json.dumps(calls[2])
    assert '"actual": 25' in calls[2][1]['content']


@pytest.mark.asyncio
async def test_exhausted_model_connection_keeps_later_questions_and_failed_slot_uncached(pipeline,monkeypatch,tmp_path):
    import httpx
    monkeypatch.setenv('DEEPTUTOR_HOME',str(tmp_path))
    items=[]
    for i in range(3):
        node=mimic_source._blueprint_question({'question_text':f'Source {i}','question_type':'short_answer'},i+1,'a'*64)
        items.append(QuizTemplate(node['question_id'],node['concept'],'short_answer','medium',source='mimic',blueprint=node))
    store=QuestionCheckpoint('alice','transport-recovery',{'model':'v1'})
    context=UnifiedContext(user_message='Generate new tasks');context.extension('question_pipeline')['checkpoint']=store
    async def generate(**kwargs):
        t=kwargs['template']
        if t is items[1]:raise httpx.ReadTimeout('retries exhausted')
        return QuizPair(t.question_id,'New question','short_answer','Answer','Proof',metadata={'review_passed':True,'blueprint_id':t.question_id})
    monkeypatch.setattr(pipeline,'_quiz_one',generate)
    result=await pipeline.run(context=context,user_message='Generate new tasks',num_questions=3,templates_override=items,stream=StreamBus())
    assert result['summary']['completed']==2 and result['summary']['failed']==1
    assert store.read(items[0],[]) and store.read(items[2],[])
    assert store.read(items[1],[]) is None


@pytest.mark.asyncio
async def test_heap_question_mentioning_complete_tree_does_not_require_target_node_facts(pipeline,monkeypatch):
    item=template('choice',question_text='Which sequence is a heap?',concept='Minimum heap')
    q={'question_type':'choice','question':'Which level-order sequence of a complete binary tree is a min-heap?',
       'options':{'A':'1,2,3','B':'3,2,1'},'correct_answer':'A','explanation':'Every parent in A is smaller.'}
    solve={'well_posed':True,'requires_computation':True,'solution':'A',
        'calculations':[{'expression':'is_heap([1,2,3])','expected':True}],
        'option_checks':{'A':'is_heap([1,2,3])','B':'is_heap([3,2,1])'}}
    review=dict(concept_match=True,novel_question=True,answer_valid=True,requirements_met=True,
        same_task_rephrased=False,task_change_evidence='New array',independent_solution='A')
    step=AsyncMock(side_effect=[LabeledStepResult(label='FINISH',text=json.dumps(x)) for x in [solve,review]])
    monkeypatch.setattr(pipeline,'_run_labeled_step',step)
    assert await pipeline._review_mimic(item,q,'',StreamBus(),object(),[])==[]
    assert step.await_count==2


@pytest.mark.asyncio
async def test_content_repair_uses_frozen_text_model_without_source_figure(pipeline, monkeypatch):
    pipeline.llm_config.edu_text_model = {'model': 'text-repair', 'binding': 'openai',
        'api_key': 'fake', 'base_url': 'https://example.invalid'}
    source = template()
    from dataclasses import replace
    source = replace(source, source_images=[Attachment(type='image', filename='old.png', mime_type='image/png', base64='b2xk')])
    observed=[]
    async def step(self, **kwargs):
        observed.append((self.model, json.dumps(kwargs['messages'])))
        return LabeledStepResult(label='FINISH', text='{"question":"new instance","correct_answer":"fixed","explanation":"proof"}')
    monkeypatch.setattr(QuestionPipeline, '_run_labeled_step', step)
    result = await pipeline._repair_quiz_payload(template=source,
        payload={'question':'new input 314'}, issues=['answer_valid'], requirements='keep concept',
        stream=StreamBus(), client=object())
    assert result['correct_answer']=='fixed'
    assert observed[0][0]=='text-repair'
    assert '314' in observed[0][1] and 'keep concept' in observed[0][1]
    assert 'image_url' not in observed[0][1] and 'b2xk' not in observed[0][1]
    assert pipeline.model=='offline'


@pytest.mark.parametrize('labels', [['front', 'back'], ['0', '1', '2', '3', '4'], ['a', 'b']])
def test_source_inline_and_numeric_choices_keep_order_and_count(labels):
    source = 'Choose one of ' + ', '.join(labels)
    node = mimic_source._blueprint_question({'question_text': source, 'question_type': 'choice',
        'option_keys': labels}, 1, 'a' * 64)
    assert node['source_text'] == source
    assert node['source_option_keys'] == labels
    assert node['option_keys'] == [chr(65 + i) for i in range(len(labels))]
    assert json.loads(node['reference_question'].split('original label): ')[1]) == dict(zip(node['option_keys'], labels))
    item = QuizTemplate(node['question_id'], node['concept'], 'choice', 'medium', blueprint=node)
    assert item.blueprint['option_keys'] == node['option_keys']


@pytest.mark.parametrize('labels', [['front', 'front'], ['', 'back'], [['bad'], 'back'], ['only']])
def test_source_ambiguous_choice_labels_still_fail(labels):
    with pytest.raises(ValueError, match='Invalid source option keys'):
        mimic_source._blueprint_question({'question_text': 'Choose', 'question_type': 'choice',
            'option_keys': labels}, 1, 'a' * 64)


@pytest.mark.parametrize('invalid', [[{'source_start_line': 1}], ['L1'], [0], [99], None])
def test_incomplete_anchors_get_one_bounded_correction(monkeypatch, tmp_path, invalid):
    q = {'question_number': '1', 'question_text': 'Explain sorting', 'question_type': 'short_answer',
         'source_start_line': 1, 'source_end_line': 1}
    calls = []
    def extract(*args):
        calls.append(args[0])
        return {'questions': [q], 'incomplete_questions': invalid if len(calls) == 1 else []}
    monkeypatch.setattr(extractor, '_extract_question_window', extract)
    result = extractor.extract_questions_with_llm('Explain sorting\n', [], tmp_path, '', '', 'offline')
    assert len(result) == 1 and len(calls) == 2
    assert 'incomplete_questions must be an array' in calls[1]


def test_repeated_invalid_partial_anchors_remain_failure(monkeypatch, tmp_path):
    calls = []
    def extract(*args):
        calls.append(args)
        return {'questions': [], 'incomplete_questions': ['L1']}
    monkeypatch.setattr(extractor, '_extract_question_window', extract)
    with pytest.raises(ValueError, match='Invalid partial-question anchors'):
        extractor.extract_questions_with_llm('A question\n', [], tmp_path, '', '', 'offline')
    assert len(calls) == 2


def test_partial_image_tail_reconciliation_includes_parent_stem(monkeypatch, tmp_path):
    calls = []
    def extract(window, *args):
        calls.append(window)
        q = {'question_number': '1', 'question_text': 'Match the five labels', 'question_type': 'fill_in_blank',
             'source_start_line': 1, 'source_end_line': 2 if len(calls) == 1 else 5}
        if len(calls) > 1:
            assert '[L1] Question 1' in window and '[L4] answer box' in window
        return {'questions': [q], 'incomplete_questions': [4] if len(calls) == 1 else []}
    monkeypatch.setattr(extractor, '_extract_question_window', extract)
    result = extractor.extract_questions_with_llm('Question 1\nMatch labels\nfigure\nanswer box\nmore boxes\n', [], tmp_path, '', '', 'offline')
    assert len(calls) == 2 and len(result) == 1 and result[0]['source_end_line'] == 5


@pytest.mark.parametrize('reverse', [False, True])
def test_nested_heading_and_stem_spans_are_one_question(monkeypatch, tmp_path, reverse):
    def question(first,last):
        return {'question_number':'5','question_text':'Sorting task','question_type':'compound',
                'children':[{'question_type':'short_answer','question_text':'Part one'}],
                'source_start_line':first,'source_end_line':last}
    qs=[question(1,6),question(3,4),question(8,9)]
    if reverse:qs.reverse()
    monkeypatch.setattr(extractor,'_extract_question_window',lambda *args: {'questions':qs,'incomplete_questions':[]})
    result=extractor.extract_questions_with_llm(''.join(f'line {i}\n' for i in range(10)),[],tmp_path,'','','offline')
    assert [(x['source_start_line'],x['source_end_line']) for x in result]==[(1,6),(8,9)]


@pytest.mark.parametrize('as_partial', [False, True])
def test_numbered_administrative_form_is_excluded_even_with_points(monkeypatch,tmp_path,as_partial):
    form='Write your name and NetID; fill in the exam room and precept; write and sign the Honor Code pledge.'
    questions=[{'question_number':'2','question_text':'Compute a tree path','question_type':'short_answer',
                'source_start_line':3,'source_end_line':3}]
    if not as_partial:questions.insert(0,{'question_number':'1','question_text':form,'question_type':'short_answer',
                                        'source_start_line':1,'source_end_line':2})
    monkeypatch.setattr(extractor,'_extract_question_window',lambda *args:{'questions':questions,'incomplete_questions':[1] if as_partial else []})
    result=extractor.extract_questions_with_llm('1. Initialization (1 point)\n'+form+'\nCompute a tree path\n',[],tmp_path,'','','offline')
    assert len(result)==1 and result[0]['question_number']=='2'


def test_empty_compound_is_corrected_before_extraction_can_be_cached(monkeypatch,tmp_path):
    calls=[]
    def extract(window,*args):
        calls.append(window)
        children=[] if len(calls)==1 else [{'question_type':'short_answer','question_text':'Part one'}]
        return {'questions':[{'question_number':'4','question_text':'Match entries','question_type':'compound',
                              'children':children,'source_start_line':1,'source_end_line':1}], 'incomplete_questions':[]}
    monkeypatch.setattr(extractor,'_extract_question_window',extract)
    result=extractor.extract_questions_with_llm('Match entries\n',[],tmp_path,'','','offline')
    assert len(calls)==2 and len(result[0]['children'])==1
    assert 'Every compound MUST contain all ordered children' in calls[1]


def test_explicit_option_pairs_inside_compound_keep_keys_and_text(pipeline):
    t=template('compound',children=[{'question_text':'front or back','question_type':'choice','option_keys':['front','back']}])
    payload={'question':'Shared stack case','correct_answer':'Child 1: A','explanation':'Shared proof','children':[
        {'question':'Choose the end','correct_answer':'A','explanation':'LIFO','options':[{'key':'A','text':'front'},{'key':'B','text':'back'}]}]}
    normalized=pipeline._normalize_quiz_payload(t,payload)
    assert normalized['children'][0]['options']=={'A':'front','B':'back'}
    assert not pipeline._collect_quiz_issues(t,normalized)


@pytest.mark.parametrize('pairs', [
    [{'key':'A','text':'one'},{'key':'A','text':'two'}],
    [{'key':'A','text':'one'},{'key':'C','text':'two'}],
    [{'key':'A','text':'one'}],
    [{'key':'A','text':'one'},{'key':'B','text':''}],
    ['one','two'],
])
def test_ambiguous_or_incomplete_option_lists_still_fail(pipeline,pairs):
    t=template('choice',option_keys=['A','B'])
    normalized=pipeline._normalize_quiz_payload(t,{'question':'Choose','correct_answer':'A','explanation':'Proof','options':pairs})
    assert 'choice_option_keys_mismatch' in pipeline._collect_quiz_issues(t,normalized)


@pytest.mark.parametrize('wrapper', ['{}', '```json\n{}\n```', 'FINISH\n{}', 'Response:\n```json\n{}\n```\nDone.'])
def test_json_answers_preserve_embedded_code_fences(wrapper):
    payload = {'solution': 'Use:\n```python\ndef select(root):\n    return root.key\n```',
               'question': 'Fill the program', 'children': [{'correct_answer': '```x```'}]}
    assert QuestionPipeline._parse_quiz_payload(wrapper.format(json.dumps(payload))) == payload


def test_broken_json_with_code_fences_is_not_salvaged_as_an_answer():
    assert QuestionPipeline._parse_quiz_payload('{"solution":"```python\nmalformed') == {}


@pytest.mark.parametrize('repair', [True, False])
def test_lettered_subquestions_under_explicit_parent_are_not_flattened(monkeypatch,tmp_path,repair):
    calls=[]
    flat=[{'question_number':'1'+letter,'question_text':'Part '+letter,'question_type':'short_answer',
           'source_start_line':i+2,'source_end_line':i+2} for i,letter in enumerate('ab')]
    def extract(window,*args):
        calls.append(window)
        questions=flat
        if repair and len(calls)>1:
            assert 'numbered parent 1 was flattened' in window
            questions=[{'question_number':'1','question_text':'Linked lists','question_type':'compound',
                        'source_start_line':1,'source_end_line':3,'children':flat}]
        return {'questions':questions,'incomplete_questions':[]}
    monkeypatch.setattr(extractor,'_extract_question_window',extract)
    if repair:
        result=extractor.extract_questions_with_llm('## 1 Linked lists\na) Code\nb) Complexity\n',[],tmp_path,'','','offline')
        assert len(result)==1 and len(result[0]['children'])==2
    else:
        with pytest.raises(ValueError,match='numbered parent 1 was flattened'):
            extractor.extract_questions_with_llm('## 1 Linked lists\na) Code\nb) Complexity\n',[],tmp_path,'','','offline')
    assert len(calls)==2


@pytest.mark.parametrize('heading', ['## 1 Multiple choice', '## Topic'])
def test_numbered_section_does_not_merge_ordinary_questions(monkeypatch,tmp_path,heading):
    qs=[{'question_number':str(i+1),'question_text':'Question','question_type':'choice',
         'source_start_line':i+2,'source_end_line':i+2} for i in range(2)]
    monkeypatch.setattr(extractor,'_extract_question_window',lambda *a:{'questions':qs,'incomplete_questions':[]})
    result=extractor.extract_questions_with_llm(heading+'\n1. Choice\n2. Choice\n',[],tmp_path,'','','offline')
    assert len(result)==2


@pytest.mark.parametrize('answer,kind,expected', [(False,'concept','false'), (True,'concept','true'), (0,'short_answer','0')])
def test_scalar_false_and_zero_answers_survive_normalization(pipeline,answer,kind,expected):
    t=template(kind);p=pipeline._normalize_quiz_payload(t,{'question':'Evaluate the statement','correct_answer':answer,'explanation':'Evidence'})
    assert p['correct_answer']==expected
    assert not pipeline._collect_quiz_issues(t,p)


def test_false_answer_inside_compound_is_not_missing(pipeline):
    t=template('compound',children=[{'question_text':'A claim','question_type':'concept'}])
    p=pipeline._normalize_quiz_payload(t,{'question':'Assess claims','correct_answer':'false','explanation':'Evidence',
        'children':[{'question':'A claim','correct_answer':False,'explanation':'Counterexample'}]})
    assert p['children'][0]['correct_answer']=='false'
    assert not pipeline._collect_quiz_issues(t,p)


def test_null_answer_remains_missing(pipeline):
    t=template('concept');p=pipeline._normalize_quiz_payload(t,{'question':'A claim','correct_answer':None,'explanation':'Evidence'})
    assert 'missing_correct_answer' in pipeline._collect_quiz_issues(t,p)
