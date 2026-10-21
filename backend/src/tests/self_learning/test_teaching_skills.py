"""The teaching workflow reaches actual model turns, including resume and failure."""
import json
import shutil

import pytest

from app.self_learning.agent_runtime import LearningAgentRuntime
from app.self_learning.context_builder import ContextBuilder
from app.self_learning import teaching_skills
from app.services.tutoring_response_policy import TUTORING_RESPONSE_POLICY
from tests.self_learning.test_agent_runtime import Model, accept, request, agent_service
from tests.self_learning.test_session_api import live_service, repository
from tests.self_learning.test_classroom_context import material as classroom_material


@pytest.mark.parametrize('kind,mode,body', [
    ('report', 'document', {'title': '报告', 'content': '变量是名称与对象的绑定。'}),
    ('quiz', 'quiz', {'title': '习题', 'questions': [{'stem': 'x = 1 后 x 的值是什么？'}]}),
    ('classroom', 'classroom', classroom_material()),
])
def test_each_mode_is_loaded_and_version_is_persisted(agent_service, kind, mode, body):
    svc = agent_service
    svc.manager.save_generated_material('course', kind, 'teaching', body,
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    req = request()
    req.reading_context.resource_ref.material_type = kind
    req.reading_context.resource_ref.material_id = 'teaching'
    first = accept(svc, req)
    model = Model()
    LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).run_once()
    turn = svc.turns.get('alice', first['turn_id'])
    assert turn['status'] == 'succeeded', turn
    skill = teaching_skills.load_teaching_skill(kind)
    instructions = json.loads(model.messages[0])[0]['content']
    assert skill['instructions'] in instructions
    assert TUTORING_RESPONSE_POLICY in instructions
    assert instructions.count('<teaching_skill ') == 1
    assert turn['result']['teaching_skill'] == {k: skill[k] for k in ('name', 'version', 'mode')}
    assert turn['result']['teaching_skill']['mode'] == mode
    for other in {'document', 'quiz', 'classroom'} - {mode}:
        text = (teaching_skills.SKILLS_ROOT / teaching_skills.SKILL_NAME / 'references' / f'{other}.md').read_text().strip()
        assert text not in instructions


def test_missing_skill_stops_before_model_call(agent_service, tmp_path, monkeypatch):
    monkeypatch.setattr(teaching_skills, 'SKILLS_ROOT', tmp_path)
    first = accept(agent_service)
    model = Model()
    LearningAgentRuntime(agent_service, agent_service.turn_repository, lambda _: model).run_once()
    turn = agent_service.turns.get('alice', first['turn_id'])
    assert turn['error_code'] == 'TEACHING_SKILL_UNAVAILABLE'
    assert model.messages == []
    assert agent_service.room('course', 'alice')['chapters']


def test_checkpoint_resumes_with_its_original_skill(agent_service, tmp_path, monkeypatch):
    svc = agent_service
    first = accept(svc)
    claim = svc.turn_repository.get('alice', first['turn_id'])
    packet = ContextBuilder(svc).build(claim)
    original = packet['teaching_skill'].copy()
    target = tmp_path / teaching_skills.SKILL_NAME
    shutil.copytree(teaching_skills.SKILLS_ROOT / teaching_skills.SKILL_NAME, target)
    with (target / 'references/document.md').open('a') as f:
        f.write('\n新规则仅用于新轮次。\n')
    monkeypatch.setattr(teaching_skills, 'SKILLS_ROOT', tmp_path)
    assert teaching_skills.load_teaching_skill('report')['version'] != original['version']
    # Resume the stored packet, without replaying earlier model/tool operations.
    import asyncio
    claim['checkpoint'] = {'packet': packet, 'rounds': 1, 'tools': 0, 'pending': [], 'repair_used': False}
    claim = {**svc.turn_repository.claim(), 'checkpoint': claim['checkpoint']}
    model = Model()
    result = asyncio.run(LearningAgentRuntime(svc, svc.turn_repository, lambda _: model).execute(claim))
    assert result['teaching_skill'] == original
    assert '新规则仅用于新轮次' not in model.messages[0]


def test_followup_keeps_topic_and_successful_conversation(agent_service):
    svc = agent_service
    model = Model()
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: model)
    for question in ['请解释这段内容。', '我们现在在围绕着什么在提问', '围绕着哪个知识点']:
        accepted = accept(svc, request(question))
        runtime.run_once()
        result = svc.turns.get('alice', accepted['turn_id'])
        assert result['status'] == 'succeeded'
        messages = json.loads(model.messages[-1])
        data = json.loads(messages[1]['content'].split('\n', 1)[1])
        assert data['learning_context']['course']['title'] == 'Python'
        assert data['learning_context']['current_topic']['title'] == '变量'
        assert messages[-1]['content'] == question
    # Course-wide history prefixes the original question with its saved location.
    assert any(m['role'] == 'user' and m['content'].split('\n')[-1] == '请解释这段内容。' for m in messages)
    assert any(m['role'] == 'user' and m['content'].split('\n')[-1] == '我们现在在围绕着什么在提问' for m in messages)
