from types import SimpleNamespace
from app.course_preparation.production_stages import ProductionStages
from app.course_preparation.tool_registry import digest


def test_saturated_videos_do_not_block_later_reports_and_quizzes():
    specs = [{'node_id': f'n{i}', 'resource_type': kind} for i in range(6) for kind in ('classroom','report','quiz')]
    videos = [s for s in specs if s['resource_type'] == 'classroom'][:4]
    checkpoint = {'resource_specs': specs, 'generation_receipts': {digest(s): digest(s) for s in videos}}
    submitted = []
    repo = SimpleNamespace(begin_action=lambda *a: {'status':'pending','replay':False,'action_id':'a'}, finish_action=lambda *a: None)
    generation = SimpleNamespace(read_result=lambda *a: {'status':'running'}, submit=lambda ctx,spec,action: submitted.append(spec) or digest(spec))
    stages = ProductionStages(repo, generation, None, concurrency=8)
    stages.prepare_specifications = lambda ctx: checkpoint
    stages.produce(SimpleNamespace(owner_user_id='u'))
    assert len(submitted) == 4
    assert all(s['resource_type'] != 'classroom' for s in submitted)


def test_multiple_nodes_start_without_waiting_for_first_video():
    specs = [{'node_id': f'n{i}', 'resource_type': kind} for i in range(4) for kind in ('classroom','report','quiz')]
    submitted = []
    repo = SimpleNamespace(begin_action=lambda *a: {'status':'pending','replay':False,'action_id':'a'}, finish_action=lambda *a: None)
    generation = SimpleNamespace(submit=lambda ctx,spec,action: submitted.append(spec) or digest(spec))
    stages = ProductionStages(repo,generation,None,concurrency=8)
    stages.prepare_specifications = lambda ctx: {'resource_specs': specs}
    stages.produce(SimpleNamespace(owner_user_id='u'))
    assert len(submitted) == 8 and len({s['node_id'] for s in submitted}) == 4
    assert submitted[0]['resource_type'] == 'classroom'
    assert all(s['resource_type'] != 'classroom' for s in submitted[1:])


def _dispatch(specs, statuses, monkeypatch, *, total=8, retry=None):
    monkeypatch.setattr('core.config.Config.COURSE_PREPARATION_VIDEO_CONCURRENCY', 8)
    receipts = {digest(s): digest(s) for s in specs if digest(s) in statuses}
    submitted = []
    repo = SimpleNamespace(begin_action=lambda *a: {'status':'pending','replay':False,'action_id':a[1]}, finish_action=lambda *a: None)
    generation = SimpleNamespace(read_result=lambda owner, key: {'status':statuses[key]},
        submit=lambda ctx,spec,action: submitted.append(spec) or digest(spec))
    stages = ProductionStages(repo, generation, None, concurrency=total)
    checkpoint = {'resource_specs':specs, 'generation_receipts':receipts}
    if retry: checkpoint['retry_node_id'] = retry
    stages.prepare_specifications = lambda ctx: checkpoint
    stages.produce(SimpleNamespace(owner_user_id='u'))
    return submitted


def test_fifth_video_starts_while_first_four_are_running(monkeypatch):
    videos = [{'node_id':f'n{i}', 'resource_type':'classroom'} for i in range(5)]
    lights = [{'node_id':f'n{i}', 'resource_type':kind} for i in range(5) for kind in ('report','quiz')]
    statuses = {digest(s):'running' for s in videos[:4]}
    statuses.update({digest(s):'draft' for s in lights})
    assert _dispatch(videos+lights, statuses, monkeypatch) == videos[4:]


def test_borrows_all_eight_slots_after_light_work_finishes(monkeypatch):
    videos = [{'node_id':f'n{i}', 'resource_type':'classroom'} for i in range(9)]
    light = {'node_id':'n0', 'resource_type':'report'}
    assert len(_dispatch(videos+[light], {digest(light):'draft'}, monkeypatch)) == 8


def test_pending_and_running_lights_reserve_only_the_capacity_they_need(monkeypatch):
    videos = [{'node_id':f'n{i}', 'resource_type':'classroom'} for i in range(9)]
    light = {'node_id':'n0', 'resource_type':'quiz'}
    for status in ('pending','running'):
        assert len(_dispatch(videos+[light], {digest(light):status}, monkeypatch)) == 7


def test_two_lights_pending_allow_six_videos_and_retry_scope_is_preserved(monkeypatch):
    videos = [{'node_id':f'n{i}', 'resource_type':'classroom'} for i in range(9)]
    lights = [{'node_id':'n0', 'resource_type':k} for k in ('report','quiz')]
    statuses = {digest(s):'running' for s in lights}
    assert len(_dispatch(videos+lights, statuses, monkeypatch)) == 6
    assert _dispatch(videos+lights, {digest(s):'draft' for s in lights}, monkeypatch, retry='n5') == [videos[5]]


def test_single_slot_never_deadlocks_light_or_video(monkeypatch):
    specs = [{'node_id':'n0', 'resource_type':k} for k in ('classroom','quiz')]
    assert _dispatch(specs, {}, monkeypatch, total=1) == specs[:1]
    assert _dispatch(specs, {digest(specs[0]):'draft'}, monkeypatch, total=1) == specs[1:]
