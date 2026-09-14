from app.chat.persistence.interaction_state import project_interaction


def plan(identifier='lesson', revision=1):
    return {'harness_outline': {'outline_id': identifier, 'revision': revision},
            'workflow': {'type': 'lesson_plan', 'status': 'awaiting_confirm'}}


def draft(revision=1):
    return {'artifact_revision': {'draft': {'draft_id': 'old', 'revision': revision}}}


def test_task_switch_suspends_old_confirmation_and_reading_does_not_resume():
    state = project_interaction(None, draft())
    state = project_interaction(state, plan())
    assert state['foreground'] == 'plan:lesson'
    assert state['tasks']['draft:old']['status'] == 'suspended'
    unchanged = project_interaction(state, {'artifact_revision': {'status': 'answered', 'artifact_reference': {'artifact_id': 'old'}}})
    assert unchanged == state
    restored = project_interaction(state, draft(2))
    assert restored['foreground'] == 'draft:old'
    assert restored['tasks']['plan:lesson']['status'] == 'suspended'
    assert restored['tasks']['draft:old']['revision'] == 2


def test_late_background_completion_cannot_steal_new_plan():
    state = project_interaction(None, {'task_id': 'first', 'workflow': {'type': 'report', 'status': 'running'}})
    state = project_interaction(state, plan())
    result = project_interaction(state, {'task_id': 'first', 'workflow': {'type': 'report', 'status': 'completed'}})
    assert result['foreground'] == 'plan:lesson'
    assert result['tasks']['job:first']['status'] == 'completed'
    assert result['tasks']['plan:lesson']['status'] == 'awaiting_confirm'


def test_replay_does_not_advance_checkpoint_revision():
    state = project_interaction(None, plan())
    assert project_interaction(state, plan()) == state
    updated = project_interaction(state, plan(revision=2))
    assert updated['version'] == state['version'] + 1


def test_conversation_turn_serializes_competing_requests(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from types import SimpleNamespace
    from app.chat.persistence.interaction_state import conversation_turn, Config
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path)
    request = SimpleNamespace(owner='teacher', conversation_id='same')
    attempted, entered = Event(), Event()
    def competing():
        attempted.set()
        with conversation_turn(request):
            entered.set()
    with ThreadPoolExecutor() as pool:
        with conversation_turn(request):
            future = pool.submit(competing)
            assert attempted.wait(2)
            assert not entered.wait(.1)
        future.result(timeout=2)
    assert entered.is_set()


def test_submission_links_exact_plan_revision_to_background_job():
    state = project_interaction(None, plan())
    result = project_interaction(state, {'task_id': 'job1', 'workflow': {'type': 'lesson_plan', 'status': 'running'},
        'trace': {'tool_events': [{'ok': True, 'tool': 'submit_resource', 'data':
            {'outline_id': 'lesson', 'revision': 1, 'task_id': 'job1'}}]}})
    assert result['tasks']['plan:lesson']['status'] == 'submitted'
    assert result['tasks']['plan:lesson']['job_id'] == 'job1'
    assert result['foreground'] == 'job:job1'
