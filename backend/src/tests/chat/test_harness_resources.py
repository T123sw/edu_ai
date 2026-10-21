import copy
from types import SimpleNamespace

import pytest

from app.chat.harness.runtime import HarnessRuntime
from app.chat.harness.store import HarnessStore
from app.chat.harness.reviewed_resource import digest, verified_resource, ReviewedResourceGenerator
from app.chat.harness.reviewed_report import CRITERIA
from tests.chat.test_harness_runtime import request, toolset, OrganizedGateway as BaseOrganizedGateway, ref

class OrganizedGateway(BaseOrganizedGateway):
    def chat(self, messages, **kwargs):
        import json
        prompt = json.loads(messages[-1]['content'])
        raw = super().chat(messages, **kwargs)
        kind = prompt.get('resource_type')
        if 'section_count' not in prompt or kind not in {'lesson_plan', 'classroom'}:
            return raw
        content = json.loads(raw)
        for chapter in content['chapters']:
            chapter.pop('points', None)
            chapter['duration_minutes'] = 25 / 3
            if kind == 'lesson_plan':
                chapter.update(teacher_activity='提出边界问题并示范', student_activity='独立追踪边界更新', assessment='检查退出条件是否正确')
            else:
                chapter.update(learning_goal='解释循环退出条件', screen_content='投屏区间变化过程', narration='逐步讲解边界更新', interaction='学生预测下一步边界')
        if kind == 'lesson_plan':
            content.update(objectives=['解释边界更新'], duration_minutes=25)
        return json.dumps(content)


KINDS = ['lesson_plan', 'blog', 'quiz', 'flashcard', 'graph', 'game', 'classroom']


@pytest.mark.parametrize('kind', KINDS)
def test_resource_plan_confirmation_recovery_submission(tmp_path, kind):
    store, calls = HarnessStore(tmp_path), []
    req = request(question='先给教学资源方案，确认后再生成', action_hint='generate.' + kind, request_id='outline-turn')
    assert HarnessRuntime.supports(req)
    with store.session(req) as session:
        tools = toolset(req, session, gateway=OrganizedGateway())
        args = {'resource_type': kind, 'subject': '二分查找', 'requirements': '保留用户数量与语言'}
        org = tools.call('organize_resource_content', args)
        assert org['ok'], org
        outline = tools.call('draft_resource_outline', {**args, 'organization_id': org['data']['organization_id'], 'section_count': 3, 'require_confirmation': True, 'classroom_options': {'enable_tts': False, 'include_visuals': False, 'duration_minutes': 25}})
        assert outline['ok'], outline
        assert not tools.call('submit_resource', ref(outline['data']))['ok']
        result = HarnessRuntime._result(req, '不能出现的另一份大纲', tools)
        assert result['workflow']['type'] == kind
        assert result['message']['content'].startswith(outline['data']['markdown'])
        assert result['action']['name'] == 'generate.' + kind
    req = request(question='Sí, adelante', request_id='confirm-turn')
    with store.session(req) as session:
        tools = toolset(req, session, submit=lambda command: calls.append(command) or SimpleNamespace(edu_job_id='job-' + kind))
        result = tools.call('submit_resource', ref(outline['data']))
        assert result['ok'], result
        assert tools.call('submit_resource', ref(outline['data']))['ok']
        assert len(calls) == 1
        assert calls[0].resource_type == kind
        assert calls[0].config['harness_organization']['resource_type'] == kind
        assert calls[0].config['focus'] == args['requirements']
        assert calls[0].config['harness_execution_context']['decision']['user_message'] == req.question
        assert HarnessRuntime._result(req, 'raw job ID', tools)['workflow']['type'] == kind


def test_resource_organization_type_and_confirmation_cannot_be_reused(tmp_path):
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, gateway=OrganizedGateway())
        args = {'resource_type': 'quiz', 'subject': '二分查找'}
        org = tools.call('organize_resource_content', args)['data']
        result = tools.call('draft_resource_outline', {**args, 'resource_type': 'flashcard', 'organization_id': org['organization_id']})
        assert not result['ok']
        assert session.data['outlines'] == {}


def artifact(content, kind='flashcard'):
    return {'content': content, 'generation_state': {'resource_review': {
        'decision': 'pass', 'method': 'model_review', 'resource_type': kind,
        'content_sha256': digest(kind, content), 'checks': [{'criterion': c, 'passed': True} for c in CRITERIA]}}}


def test_query_checks_version_owner_course_and_cancel_authority(tmp_path):
    content = {'cards': [{'front': '数组索引访问复杂度？', 'back': 'O(1)'}]}
    material = artifact(content)
    job = SimpleNamespace(kind='generate_flashcard', owner_user_id='alice', course_id='course1',
        status='succeeded', progress=100, result_ref={'course_id': 'course1', 'material_type': 'flashcard', 'material_id': 'f1'}, input_summary={})
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, get_job=lambda tid: job, read_artifact=lambda ref, owner: material)
        result = tools.call('query_resource_job', {'task_id': 'external'})
        assert result['data']['artifact']['content'] == content
        assert not tools.call('query_report_job', {'task_id': 'external'})['ok']
        assert not tools.call('cancel_resource_job', {'task_id': 'external'})['ok']
        material['content']['cards'][0]['back'] = 'O(n)'
        assert tools.call('query_resource_job', {'task_id': 'external'})['data']['verification']['decision'] == 'fail'
        job.owner_user_id = 'bob'
        assert not tools.call('query_resource_job', {'task_id': 'external'})['ok']


def test_classroom_job_reports_structural_validation_without_claiming_model_review(tmp_path):
    from app.chat.harness.reviewed_resource import review_classroom
    from tests.course_preparation.test_openmaic_native_integration import native_scene
    content, receipt = review_classroom(native_scene('interactive', {'html': '<button>观察</button>'}), {})
    material = {**content, 'generation_state': {'resource_review': receipt}}
    job = SimpleNamespace(kind='generate_classroom', owner_user_id='alice', course_id='course1',
        status='succeeded', progress=100, result_ref={'course_id': 'course1', 'classroom_id': 'c1'}, input_summary={})
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, get_job=lambda _: job, read_artifact=lambda *_: material)
        result = tools.call('query_resource_job', {'task_id': 'external'})
        assert result['data']['verification'] == {'decision': 'pass',
            'checks': 'version_bound_structural_validation', 'semantic_review': 'skipped'}


def test_independent_review_repairs_real_content_and_binds_final_version():
    import json
    class Gateway:
        def __init__(self): self.writes = 0
        def chat(self, messages, **kwargs):
            if 'schema' not in json.loads(messages[-1]['content']):
                self.writes += 1
                return json.dumps({'cards': [{'front': '2+3=?', 'back': '6' if self.writes == 1 else '5'}]})
            return json.dumps({'checks': [{'criterion': c, 'passed': self.writes > 1, 'reason': '实际核验二加三等于五'} for c in CRITERIA],
                               'blocking_issues': ['2+3=5'] if self.writes == 1 else [], 'suggestions': []})
    gateway = Gateway()
    progress = []
    result = ReviewedResourceGenerator(gateway, progress=lambda *event: progress.append(event)).generate(SimpleNamespace(resource_type='flashcard', title='加法'), job_id='j', config_snapshot_id='cfg')
    assert gateway.writes == 2
    assert {item[1] for item in progress} == {'generating', 'reviewing', 'revising'}
    assert [item[0] for item in progress] == sorted(item[0] for item in progress)
    final = result['artifacts'][0]
    assert verified_resource(final, 'flashcard')
    final['content']['cards'][0]['back'] = '6'
    assert not verified_resource(final, 'flashcard')


def test_non_report_outline_can_revisit_units_and_use_one_group(tmp_path):
    import json
    class RevisitGateway(OrganizedGateway):
        def chat(self, messages, **kwargs):
            prompt = json.loads(messages[-1]['content'])
            if 'section_count' in prompt:
                return json.dumps({'chapters': [{'title': '活动与复习', 'points': ['问题与练习'], 'unit_indices': [0, 1, 2, 0]}]})
            return super().chat(messages, **kwargs)
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, gateway=RevisitGateway())
        args = {'resource_type': 'blog', 'subject': '二分查找'}
        org = tools.call('organize_resource_content', args)['data']
        result = tools.call('draft_resource_outline', {**args, 'organization_id': org['organization_id'], 'section_count': 1})
        assert result['ok'], result
        assert result['data']['chapters'][0]['unit_indices'] == [0, 1, 2, 0]


def test_native_classroom_receipt_does_not_claim_semantic_review():
    from app.chat.harness.reviewed_resource import review_classroom
    from tests.hyperframes.test_context_serving import lesson
    content=lesson()
    reviewed,audit=review_classroom(content,{})
    assert reviewed==content
    assert audit['decision']=='skipped'
    assert verified_resource({'content':reviewed,'generation_state':{'resource_review':audit}},'classroom')


@pytest.mark.parametrize('kind', ['quiz', 'flashcard', 'graph', 'game', 'blog'])
def test_direct_resources_submit_same_turn_without_outline_and_recover(tmp_path, kind):
    req, calls = request(question='请直接生成', request_id='direct-turn'), []
    store = HarnessStore(tmp_path)
    with store.session(req) as session:
        tools = toolset(req, session, gateway=OrganizedGateway(),
            submit=lambda command: calls.append(command) or SimpleNamespace(edu_job_id='direct-job'))
        org = tools.call('organize_resource_content', {'resource_type': kind, 'subject': '二分查找'})['data']
        result = tools.call('submit_resource_direct', {'organization_id': org['organization_id']})
        assert result['ok'], result
        reply = HarnessRuntime._result(req, 'internal plan', tools)
        assert reply['task_id'] == 'direct-job' and 'harness_outline' not in reply
        assert reply['workflow']['stage'] == 'generating'
        assert session.data.get('active_outline') is None
        assert calls[0].config['confirmed_outline'] == ''
        assert calls[0].config['harness_interaction_mode'] == 'direct'
        assert calls[0].deadline_seconds == 900
    with store.session(request(request_id='retry-turn')) as session:
        tools = toolset(request(request_id='retry-turn'), session, submit=lambda command: calls.append(command))
        assert tools.call('submit_resource_direct', {'organization_id': org['organization_id']})['ok']
        assert len(calls) == 1


@pytest.mark.parametrize('kind', ['report', 'lesson_plan', 'classroom'])
def test_direct_cannot_bypass_teaching_plan_confirmation(tmp_path, kind):
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, gateway=OrganizedGateway())
        org = tools.call('organize_resource_content', {'resource_type': kind, 'subject': '二分查找'})['data']
        assert not tools.call('submit_resource_direct', {'organization_id': org['organization_id']})['ok']
        assert not session.data['outlines']


def test_classroom_submission_preserves_command_budget(monkeypatch):
    from app.chat.harness.resource_jobs import submit_classroom
    from app.services.generation_command import GenerationCommand
    from app.services import classroom_service
    captured = {}
    async def submit(**kwargs):
        captured.update(kwargs)
        return 'submitted'
    monkeypatch.setattr(classroom_service, 'submit_classroom_generation_job', submit)
    command = GenerationCommand(resource_type='classroom', course_id='course-1', owner_user_id='teacher-a',
        scope_type='course', idempotency_key='classroom-budget', deadline_seconds=1800, config={'title': '数组', 'focus': '随机访问',
        'confirmed_outline': '三场景', 'audience': '初学者', 'research_context': '',
        'harness_chapters': [{}, {}, {}], 'classroom_options': {'enable_tts': False, 'include_visuals': False, 'duration_minutes': 5}})
    assert submit_classroom(command, object()) == 'submitted'
    assert captured['deadline_seconds'] == 1800
    assert 'scene_count' not in captured and captured['duration_minutes'] == 5
    assert captured['enable_tts'] is False and captured['include_visuals'] is False


def test_one_card_organization_needs_only_one_objective_and_unit(tmp_path):
    import json
    class OneCardGateway(OrganizedGateway):
        def chat(self, messages, **kwargs):
            payload = json.loads(messages[-1]['content'])
            if 'schema' in payload and 'section_count' not in payload:
                return json.dumps({'scope': '数组访问', 'objectives': ['回忆访问复杂度'],
                    'units': [{'title': '复杂度', 'explanation': '连续等宽数组按下标访问为 O(1)', 'objective_indices': [0]}]})
            return super().chat(messages, **kwargs)
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, gateway=OneCardGateway())
        result = tools.call('organize_resource_content', {'resource_type': 'flashcard', 'subject': '数组', 'requirements': '只要一张卡'})
        assert result['ok'], result
        assert len(result['data']['units']) == 1


def test_skill_contract_is_supplied_to_writer_and_reviewer():
    import json
    from app.chat.harness.resource_profiles import resource_contract
    captured = []
    class Gateway:
        def chat(self, messages, **kwargs):
            captured.append(messages)
            if 'schema' not in json.loads(messages[-1]['content']):
                return json.dumps({'cards': [{'front': '2+3=?', 'back': '5'}]})
            return json.dumps({'checks': [{'criterion': c, 'passed': True, 'reason': '实际核算二加三为五'} for c in CRITERIA],
                'blocking_issues': [], 'suggestions': []})
    ReviewedResourceGenerator(Gateway()).generate(SimpleNamespace(resource_type='flashcard', title='加法'), job_id='j', config_snapshot_id='c')
    assert resource_contract('flashcard') in captured[0][0]['content']
    assert json.loads(captured[1][-1]['content'])['resource_contract'] == resource_contract('flashcard')


@pytest.mark.parametrize('question', [
    {'type': 'single_choice', 'answer': 'A'},
    {'type': 'single_choice', 'options': ['甲', '乙'], 'answer': 'AB'},
    {'type': 'multiple_choice', 'options': ['甲', '甲'], 'answer': 'A'},
])
def test_quiz_native_contract_rejects_unusable_choices(question):
    from app.chat.harness.reviewed_resource import validate_resource
    with pytest.raises(ValueError):
        validate_resource('quiz', {'questions': [{'stem': '题干', 'explanation': '推导过程', **question}]})


def test_game_template_aliases_are_canonicalized_and_unknown_values_name_allowed_types():
    from app.chat.application.game_template_registry import get_game_template_spec
    assert get_game_template_spec('drag-match').game_type == 'drag_match'
    assert get_game_template_spec('memory-flip').game_type == 'memory_flip'
    with pytest.raises(ValueError, match='category_sort, drag_match, memory_flip'):
        get_game_template_spec('matching')


def test_quiz_review_blocks_wrong_distractor_explanation_even_with_correct_answer():
    import json
    from app.chat.harness.reviewed_resource import review_content
    content = {'questions': [{'type': 'single_choice', 'stem': '2000+5*8=?', 'options': ['2040', '2013'],
        'answer': 'A', 'explanation': 'A 按乘法优先计算得2040。B 是第七个元素的地址'}]}
    response = {'checks': [{'criterion': c, 'passed': True, 'reason': '逐题检查主要答案为2040'} for c in CRITERIA],
        'blocking_issues': [], 'suggestions': [], 'question_checks': [{'question_index': 0,
            'independent_solution': '2000+5*8=2040；2013是把2000、5、8相加，与第七个元素无关',
            'answer_matches': True, 'explanation_valid': False,
            'option_checks': [{'option_index': 0, 'reasoning': '乘法优先计算得2040', 'explanation_valid': True, 'independent_correct': True, 'explanation_reasoning':'已独立逐句检查解析中的主张是否对应原选项。', 'explanation_excerpt': 'A 按乘法优先计算得2040'},
                {'option_index': 1, 'reasoning': '2013来自2000+5+8，原解析不成立', 'explanation_valid': False, 'independent_correct': False, 'explanation_reasoning':'原解析不成立，2013来自相加而非第七个元素地址。', 'explanation_excerpt': 'B 是第七个元素的地址'}]}]}
    class Gateway:
        def chat(self, *args, **kwargs): return json.dumps(response)
    _, feedback = review_content('quiz', content, {}, Gateway())
    assert len(feedback) == 2 and '原解析不成立' in feedback[1]
    response['question_checks'][0]['option_checks'].pop()
    with pytest.raises(ValueError, match='option_coverage'):
        review_content('quiz', content, {}, Gateway())


def test_read_and_direct_submit_is_a_generation_result():
    from app.chat.persistence.task_status_projection import is_report_read_result
    assert not is_report_read_result({'trace': {'tool_events': [
        {'ok': True, 'tool': 'query_resource_job'}, {'ok': True, 'tool': 'submit_resource_direct'}]}})


def test_plan_edit_language_is_always_decided_by_harness(monkeypatch):
    from core.config import Config
    from app.chat.application.reply_service_v2 import ReplyServiceV2
    monkeypatch.setattr(Config, 'USE_DEEPSEEK_HARNESS', True)
    service = ReplyServiceV2(conversation_store=SimpleNamespace(storage=SimpleNamespace(get_state=lambda _: {})),
        artifact_revision_service=SimpleNamespace())
    for text in ['请把教案课时改成12分钟，先给修改后的教学方案', 'Revise the lesson timing', '修改报告']:
        assert service._model_plans(request(question=text))


def test_model_revision_handoff_uses_actual_authorized_version(tmp_path):
    job = SimpleNamespace(kind='generate_flashcard', owner_user_id='alice', course_id='course1', status='succeeded',
        result_ref={'material_id': 'cards-one', 'material_type': 'flashcard', 'course_id': 'course1'})
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, get_job=lambda _: job,
            read_artifact=lambda ref, owner: {'version': 3, 'title': '真实闪卡'})
        result = tools.call('select_resource_for_revision', {'task_id': 'j1'})
        assert result['ok'], result
        reply = HarnessRuntime._result(request(), '修订', tools)
        assert reply['resource_revision_reference']['version_id'] == 'v3'
        assert reply['resource_revision_reference']['artifact_id'] == 'cards-one'
        assert reply['action']['name'] == 'artifact.revise'
        job.owner_user_id = 'bob'
        assert not tools.call('select_resource_for_revision', {'task_id': 'j1'})['ok']


def test_classroom_unspecified_media_choices_are_not_invented(tmp_path):
    with HarnessStore(tmp_path).session(request()) as session:
        tools=toolset(request(),session,gateway=object())
        result=tools.call('draft_resource_outline',{'resource_type':'classroom','subject':'二分查找'})
        assert result['ok'],result
        assert result['data']['classroom_options']=={}
        assert result['data']['chapters']==[]
        assert result['data']['audience']==''


def test_classroom_requirement_handoff_needs_no_story_or_extra_model_review(tmp_path):
    with HarnessStore(tmp_path).session(request()) as session:
        tools=toolset(request(),session,gateway=object())
        args={'resource_type':'classroom','subject':'二分查找','requirements':'只要视频，不要题目'}
        org=tools.call('organize_resource_content',args)['data']
        result=tools.call('draft_resource_outline',{**args,'organization_id':org['organization_id']})
        assert result['ok'],result
        assert org['units']==[]
        assert result['data']['chapters']==[]
        assert args['requirements'] in result['data']['markdown']
        assert result['data']['quality']['semantic_review']=='not_performed'


def test_invalid_plan_feedback_reaches_generator_with_exact_bounds(tmp_path):
    import json
    prompts = []
    class RepairPlan(OrganizedGateway):
        def chat(self, messages, **kwargs):
            prompt = json.loads(messages[-1]['content'])
            raw = super().chat(messages, **kwargs)
            if 'section_count' in prompt:
                prompts.append(prompt)
                if len(prompts) == 1:
                    content = json.loads(raw)
                    content['chapters'][-1]['unit_indices'] = [3]
                    return json.dumps(content)
            return raw
    with HarnessStore(tmp_path).session(request()) as session:
        tools = toolset(request(), session, gateway=RepairPlan())
        args = {'resource_type': 'lesson_plan', 'subject': '二分查找'}
        org = tools.call('organize_resource_content', args)['data']
        args.update(organization_id=org['organization_id'], section_count=3, require_section_count=True)
        rejected = tools.call('draft_resource_outline', args)
        assert not rejected['ok'] and not session.data['outlines']
        accepted = tools.call('draft_resource_outline', args)
        assert accepted['ok'], accepted
        assert prompts[1]['generation_feedback'] == rejected['issues']
        assert prompts[1]['previous_attempt']['chapters'][-1]['unit_indices'] == [3]
        schema = prompts[1]['schema']
        assert 'classroom_options' not in prompts[1]
        assert accepted['data']['classroom_options'] == {}
        assert schema['properties']['chapters']['minItems'] == schema['properties']['chapters']['maxItems'] == 3
        indices = schema['$defs']['TeachingPhase']['properties']['unit_indices']['items']
        assert indices['minimum'] == 0 and indices['maximum'] == 2


def test_reshow_plan_preserves_version_and_waits_for_later_confirmation(tmp_path):
    from tests.chat.test_harness_runtime import draft
    req = request(request_id='view-again')
    store = HarnessStore(tmp_path)
    with store.session(req) as session:
        tools = toolset(req, session)
        outline = draft(tools)
        previous = copy.deepcopy(outline)
        shown = tools.call('show_resource_outline', ref(outline))
        assert shown['ok'] and shown['data']['revision'] == previous['revision']
        assert shown['data']['markdown'] == previous['markdown']
        assert not tools.call('submit_resource', ref(outline))['ok']
        result = HarnessRuntime._result(req, '模型重复文字', tools)
        assert result['harness_outline'] == {k: outline[k] for k in ('outline_id', 'revision', 'subject')}
        assert result['message']['content'].startswith(previous['markdown'])
    req = request(request_id='later-confirmation')
    with store.session(req) as session:
        assert toolset(req, session).call('submit_resource', ref(outline))['ok']


def test_classroom_review_cannot_skip_wrong_speech_even_when_screen_is_correct():
    import json
    from app.chat.harness.reviewed_resource import review_content
    content = {'scenes': [{'actions': [{'type': 'spotlight'}, {'type': 'speech', 'text': '一百万个元素的数组可访问 a[1000000]'}]}]}
    response = {'checks': [{'criterion': c, 'passed': True, 'reason': '主投屏公式正确'} for c in CRITERIA],
        'blocking_issues': [], 'suggestions': [], 'scene_checks': [{'scene_index': 0,
            'screen_reasoning': '投屏公式没有错误', 'screen_passed': True,
            'speech_checks': [{'action_index': 1, 'reasoning': '零基下标最大为999999，讲解中的访问越界', 'passed': False}]}]}
    class Gateway:
        def chat(self, *args, **kwargs): return json.dumps(response)
    _, feedback = review_content('classroom', content, {}, Gateway())
    assert len(feedback) == 1 and '访问越界' in feedback[0]
    response['scene_checks'][0]['speech_checks'] = []
    with pytest.raises(ValueError, match='speech_coverage'):
        review_content('classroom', content, {}, Gateway())


def test_incomplete_review_is_retried_without_assuming_pass():
    import json
    from app.chat.harness.reviewed_resource import review_content
    calls = []
    class Gateway:
        def chat(self, messages, **kwargs):
            calls.append(copy.deepcopy(messages))
            if len(calls) == 1: return '{"checks": ['
            return json.dumps({'checks': [{'criterion': c, 'passed': False, 'reason': '内容含有错误，不能交付'} for c in CRITERIA],
                'blocking_issues': ['具体计算错误'], 'suggestions': []})
    _, feedback = review_content('blog', '错误文章', {}, Gateway())
    assert len(calls) == 2 and '具体计算错误' in feedback
    assert calls[1][-2]['content'] == '{"checks": ['


def test_classroom_no_extra_review_preserves_native_timeline():
    from app.chat.harness.reviewed_resource import review_classroom
    from tests.hyperframes.test_context_serving import lesson
    content=lesson();original=copy.deepcopy(content)
    reviewed,_=review_classroom(content,{})
    assert reviewed==original
    assert reviewed['project']==original['project']


def test_classroom_repair_handles_include_teaching_text_without_render_metadata():
    from app.chat.harness.reviewed_resource import classroom_text_fields
    source = {'stage': {'id': 'stable', 'name': '课程'}, 'scenes': [{'id': 's1', 'type': 'slide',
        'content': {'canvas': {'elements': [{'id': 'e1', 'type': 'text', 'defaultFontName': 'Arial',
            'defaultColor': '#333', 'content': '<p>真实教学内容</p>'}]}},
        'actions': [{'id': 'a1', 'type': 'speech', 'text': '完整旁白', 'audioUrl': '/media/audio.mp3'}]}]}
    fields = classroom_text_fields(source)
    assert {f['text'] for f in fields} == {'课程', '<p>真实教学内容</p>', '完整旁白'}
    assert [f['field_id'] for f in fields] == list(range(len(fields)))


def test_whole_text_replacement_preserves_markup_and_identity_guards():
    from app.chat.harness.reviewed_resource import bind_text_replacements
    from app.artifact_revision.adapters import apply_edits
    source = {'id': 'scene1', 'text': '<b>2+3</b>：2+3=6'}
    replacements = [{'field_id': 0, 'text': '<b>2+3</b>：2+3=5'}]
    assert apply_edits(source, bind_text_replacements(source, replacements)) == {
        'id': 'scene1', 'text': '<b>2+3</b>：2+3=5'}
    assert source['text'].endswith('=6')
    with pytest.raises(ValueError, match='字段编号'):
        bind_text_replacements(source, [{'field_id': 1, 'text': 'changed identity'}])
    with pytest.raises(ValueError, match='身份'):
        apply_edits(source, [{'path': ['id'], 'before': 'scene1', 'after': 'changed'}])
    with pytest.raises(ValueError, match='一次'):
        bind_text_replacements(source, replacements * 2)


def test_classroom_no_extra_review_never_calls_reviewer_or_repairer():
    from app.chat.harness.reviewed_resource import review_classroom
    from tests.hyperframes.test_context_serving import lesson
    class Forbidden:
        def chat(self,*a,**k):raise AssertionError('No additional content reviewer')
    def repair(*a,**k):raise AssertionError('Host must not rewrite native content')
    _,audit=review_classroom(lesson(),{},gateway=Forbidden(),repair=repair)
    assert audit['decision']=='skipped'



def test_missing_speech_review_is_retried_with_explicit_coverage():
    import json
    from app.chat.harness.reviewed_resource import review_content
    calls = []
    class Gateway:
        def chat(self, messages, **kwargs):
            calls.append(copy.deepcopy(messages))
            assert json.loads(messages[1]['content'])['required_coverage'] == [{'scene_index': 0, 'speech_action_indices': [1]}]
            return json.dumps({'checks': [{'criterion': c, 'passed': True, 'reason': '逐项核算内容正确'} for c in CRITERIA],
                'blocking_issues': [], 'suggestions': [], 'scene_checks': [{'scene_index': 0,
                    'screen_reasoning': '投屏公式与计算正确', 'screen_passed': True,
                    'speech_checks': [] if len(calls) == 1 else [{'action_index': 1, 'reasoning': '二加三等于五，讲解正确', 'passed': True}]}]})
    review, feedback = review_content('classroom', {'scenes': [{'actions': [{'type': 'spotlight'}, {'type': 'speech', 'text': '2+3=5'}]}]}, {}, Gateway())
    assert len(calls) == 2 and not feedback and len(review.scene_checks[0].speech_checks) == 1
    assert 'speech_coverage_incomplete' in calls[1][-1]['content']


def test_explicit_video_constraints_pass_through_without_authoring_frames(tmp_path):
    with HarnessStore(tmp_path).session(request()) as session:
        tools=toolset(request(),session,gateway=object())
        result=tools.call('draft_resource_outline',{'resource_type':'classroom','subject':'二分查找',
            'section_count':5,'require_section_count':True,
            'classroom_options':{'duration_minutes':0.5,'enable_tts':False}})
        assert result['ok'],result
        assert result['data']['chapters']==[]
        assert '用户指定片段数量：5' in result['data']['markdown']
        assert '0.5 分钟' in result['data']['markdown']
        assert '不需要配音' in result['data']['markdown']


def test_lesson_fast_plan_uses_one_call_and_defers_review_without_bypassing_confirmation(tmp_path):
    import json
    class FastGateway:
        def __init__(self): self.calls = 0
        def chat(self, messages, **kwargs):
            self.calls += 1
            return json.dumps({'objectives': ['能计算数组元素地址'], 'duration_minutes': 5,
                'chapters': [{'title': '寻址练习', 'duration_minutes': 5,
                    'teacher_activity': '示范数组元素的寻址', 'student_activity': '独立计算元素的地址',
                    'assessment': '核对计算结果并说明依据'}]})
    store, gateway, commands = HarnessStore(tmp_path), FastGateway(), []
    req = request(request_id='fast-plan', question='生成五分钟数组教案')
    with store.session(req) as session:
        tools = toolset(req, session, gateway=gateway)
        result = tools.call('draft_resource_outline', {'resource_type': 'lesson_plan', 'subject': '数组', 'requirements': '5分钟'})
        assert result['ok'], result
        outline = result['data']
        assert gateway.calls == 1
        assert not session.data.get('organizations')
        assert outline['quality']['semantic_review'] == 'deferred_to_generation'
        assert not outline['quality']['objective_coverage']
        assert not tools.call('submit_resource', ref(outline))['ok']
        HarnessRuntime._result(req, '', tools)
    req = request(request_id='fast-confirm', question='请按这个方案开始')
    with store.session(req) as session:
        tools = toolset(req, session, submit=lambda cmd: commands.append(cmd) or SimpleNamespace(edu_job_id='fast-job'))
        submitted = tools.call('submit_resource', ref(outline))
        assert submitted['ok'], submitted
        assert submitted['data']['conversation_id'] == req.conversation_id
        assert tools.call('submit_resource', ref(outline))['ok']
        assert len(commands) == 1
        assert commands[0].config['harness_organization'] is None
        assert commands[0].config['confirmed_outline'] == outline['markdown']
        assert commands[0].config['harness_chapters'][0]['duration_minutes'] == 5


def test_fast_lesson_still_requires_requested_retrieval_and_valid_duration(tmp_path):
    import json
    req = request(capability={'allow_web': True, 'require_web': True})
    with HarnessStore(tmp_path).session(req) as session:
        tools = toolset(req, session, gateway=OrganizedGateway())
        assert not tools.call('draft_resource_outline', {'resource_type': 'lesson_plan', 'subject': '数组'})['ok']
        assert not session.data['outlines']
    class WrongDuration(OrganizedGateway):
        def chat(self, messages, **kwargs):
            content = json.loads(super().chat(messages, **kwargs))
            content['duration_minutes'] = 1
            return json.dumps(content)
    req = request()
    with HarnessStore(tmp_path / 'duration').session(req) as session:
        tools = toolset(req, session, gateway=WrongDuration())
        assert not tools.call('draft_resource_outline', {'resource_type': 'lesson_plan', 'subject': '数组'})['ok']
        assert not session.data['outlines']


def test_model_cannot_submit_plan_after_foreground_switched_to_draft(tmp_path):
    req = request(request_id='plan-turn')
    with HarnessStore(tmp_path).session(req) as session:
        tools = toolset(req, session, gateway=OrganizedGateway())
        outline = tools.call('draft_resource_outline', {'resource_type': 'lesson_plan', 'subject': '数组', 'section_count': 3})
        assert outline['ok'], outline
        HarnessRuntime._result(req, '', tools)
        req.request_id = 'confirm-turn'
        req.interaction_state = {'foreground': 'draft:other', 'tasks': {}}
        result = tools.call('submit_resource', ref(outline['data']))
        assert not result['ok']
        assert result['error'].startswith('outline_task_suspended_present_again')


@pytest.mark.parametrize('bad_first_patch', [False, True])
def test_lesson_revision_applies_exact_edits_and_preserves_review_feedback(bad_first_patch):
    import json
    initial = '# 教案\n\n## 教学目标\n计算地址。\n\n## 教学过程\n固定环节15分钟。\n答案2+3=6。'
    class Gateway:
        def __init__(self): self.writes = 0
        def chat(self, messages, **kwargs):
            data = json.loads(messages[-1]['content'])
            if 'schema' in data:
                passed = '2+3=5' in data['content']
                return json.dumps({'checks': [{'criterion': c, 'passed': passed, 'reason': '逐项核验加法算式与课时保持情况'} for c in CRITERIA],
                    'blocking_issues': [] if passed else ['将错误答案修正为2+3=5，保持课时'], 'suggestions': []})
            self.writes += 1
            if self.writes == 1: return initial
            assert data['previous_draft'] == initial
            assert any('2+3=5' in f for f in data['feedback'])
            assert '不重新输出全文' in messages[0]['content']
            before = '不存在的片段' if bad_first_patch and self.writes == 2 else '2+3=6'
            return json.dumps({'edits': [{'path': [], 'before': before, 'after': '2+3=5'}]})
    gateway = Gateway()
    result = ReviewedResourceGenerator(gateway).generate(SimpleNamespace(resource_type='lesson_plan', title='加法'), job_id='j', config_snapshot_id='c')
    final = result['artifacts'][0]
    assert final['content'] == initial.replace('2+3=6','2+3=5')
    assert verified_resource(final, 'lesson_plan')


def test_video_requirements_can_be_submitted_in_same_authorized_turn(tmp_path):
    calls=[]
    req=request(question='直接生成一次函数教学视频，只要视频', request_id='video-direct')
    with HarnessStore(tmp_path).session(req) as session:
        tools=toolset(req,session,gateway=object(),submit=lambda command:calls.append(command) or SimpleNamespace(edu_job_id='video-job'))
        result=tools.call('draft_resource_outline',{'resource_type':'classroom','subject':'一次函数','requirements':req.question})
        assert result['ok'],result
        assert tools.call('submit_resource',ref(result['data']))['ok']
        assert len(calls)==1
        assert calls[0].config['harness_chapters']==[]
        assert calls[0].config['classroom_options']=={}
