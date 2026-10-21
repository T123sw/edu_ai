import asyncio
import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from app.services.studio_learning_resources import (
    Podcast, Scenario, StudioLearningResourceGenerator, podcast_directory, render_podcast,
)
from app.services.personal_studio import namespace, PersonalStudioTaskHandler, read
from app.services.durable_task_handlers import DurableTaskExecutionError
from tests.personal_studio.test_studio import setup, context, FakeLearning


def scenario():
    return {'title': '网站变慢了', 'introduction': '你负责排查网站延迟，这是一个模拟情景。',
        'learning_objectives': ['理解先测量再优化'], 'start_id': 'start', 'scenes': [
        {'id': 'start', 'title': '先做什么', 'situation': '用户报告网站响应很慢。', 'choices': [
            {'id': 'measure', 'text': '先测量响应时间', 'feedback': '测量可区分网络与服务端耗时。', 'next_id': 'measure'},
            {'id': 'restart', 'text': '直接重启', 'feedback': '重启可能暂时恢复但丢失排查线索。', 'next_id': 'uncertain'}]},
        {'id': 'measure', 'title': '进一步定位', 'situation': '日志显示数据库耗时较高。', 'choices': [
            {'id': 'query', 'text': '检查慢查询', 'feedback': '找到了缺失索引的查询。', 'next_id': 'fixed'},
            {'id': 'cpu', 'text': '增加 Web 服务 CPU', 'feedback': '没有处理数据库瓶颈。', 'next_id': 'uncertain'}]},
        {'id': 'fixed', 'title': '完成定位', 'situation': '请求恢复正常。', 'choices': [], 'ending': '优化查询后响应更快。', 'takeaway': '测量、定位、验证，避免凭感觉优化。'},
        {'id': 'uncertain', 'title': '问题仍在', 'situation': '延迟依然不稳定。', 'choices': [], 'ending': '根因尚未确认。', 'takeaway': '先收集证据，再选择干预措施。'},
    ]}


def podcast():
    return {'title': '理解变量', 'summary': '从生活中的例子理解变量。', 'segments': [
        {'title': '从名字开始', 'text': '变量就像一个名字，它帮助我们找到所引用的对象。'},
        {'title': '换一个例子', 'text': '当名字重新绑定，我们通过这个名字找到的对象也会改变。'},
    ]}


def command(kind='scenario'):
    return {'resource_type': kind, 'course_id': namespace('alice'), 'title': '学习资源',
        'config': {'topic': '变量', 'research_context': '变量是名字到对象的绑定。'},
        'studio_context': {'studio_course_id': 'course', 'studio_chapter_id': 'variables', 'research_context': '课程实际正文'}}


class Model:
    def __init__(self, content): self.content, self.calls = content, []
    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps(self.content, ensure_ascii=False)


@pytest.mark.parametrize('mutation', ['cycle', 'missing', 'unreachable', 'duplicate', 'no_ending', 'same_target'])
def test_invalid_case_graphs_are_rejected(mutation):
    data = scenario()
    if mutation == 'cycle': data['scenes'][1]['choices'][0]['next_id'] = 'start'
    if mutation == 'missing': data['scenes'][0]['choices'][0]['next_id'] = 'missing'
    if mutation == 'unreachable': data['scenes'].append({'id': 'orphan', 'title': '多余', 'situation': '无人进入', 'choices': [], 'ending': '结束', 'takeaway': '总结'})
    if mutation == 'duplicate': data['scenes'][1]['id'] = 'start'
    if mutation == 'no_ending': data['scenes'][2]['takeaway'] = ''
    if mutation == 'same_target': data['scenes'][0]['choices'][0]['next_id'] = 'uncertain'
    with pytest.raises(ValueError): Scenario.model_validate(data)


def test_case_generation_validates_persists_and_reads_privately(setup):
    client, manager, _, user = setup
    model = Model(scenario())
    generator = StudioLearningResourceGenerator(manager, model_factory=lambda owner: model)
    handler = PersonalStudioTaskHandler(manager=manager, learning_factory=FakeLearning, learning_generator=generator)
    result = handler(command(), context())
    assert result['saved'] and result['result_ref']['material_type'] == 'scenario'
    resource = client.get('/api/personal-studio/resources/scenario/task-1')
    assert resource.status_code == 200
    assert resource.json()['studio_complete'] is True
    assert resource.json()['studio_course_id'] == 'course'
    assert '课程实际正文' in model.calls[0]['messages'][1]['content']
    user['username'] = 'bob'
    assert client.get('/api/personal-studio/resources/scenario/task-1').status_code == 404


def test_malformed_generation_never_publishes(setup):
    _, manager, _, _ = setup
    generator = StudioLearningResourceGenerator(manager, model_factory=lambda owner: Model({'title': 'incomplete'}))
    with pytest.raises(DurableTaskExecutionError, match='结构检查'):
        generator(command(), context())
    assert not manager.list_generated_materials(namespace('alice'), aggregate=True)


def test_podcast_audio_failure_keeps_draft_and_resumes_without_regenerating(setup):
    client, manager, _, user = setup
    model = Model(podcast())
    async def fail(*args): raise RuntimeError('provider unavailable')
    generator = StudioLearningResourceGenerator(manager, model_factory=lambda owner: model, audio_renderer=fail)
    with pytest.raises(DurableTaskExecutionError, match='配音'):
        generator(command('podcast'), context())
    assert not client.get('/api/personal-studio').json()['resources']
    assert client.get('/api/personal-studio/resources/podcast/task-1/audio').status_code == 409
    async def audio(content, folder, ctx):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'podcast.mp3').write_bytes(b'ID3test-audio')
    generator.audio_renderer = audio
    result = generator(command('podcast'), context())
    assert result['saved'] and len(model.calls) == 1
    detail = client.get('/api/personal-studio/resources/podcast/task-1').json()
    url = detail['content']['audio_url']
    response = client.get(url)
    assert response.status_code == 200 and response.headers['content-type'] == 'audio/mpeg'
    assert 'private' in response.headers['cache-control']
    user['username'] = 'bob'
    assert client.get(url).status_code == 404


def test_cancellation_before_generation_or_after_audio_does_not_publish(setup):
    client, manager, _, _ = setup
    model = Model(podcast())
    generator = StudioLearningResourceGenerator(manager, model_factory=lambda owner: model)
    assert generator(command('podcast'), context(cancelled=True))['canceled']
    assert not model.calls
    canceled = [False]
    async def audio(content, folder, ctx):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'podcast.mp3').write_bytes(b'ID3test')
        canceled[0] = True
    generator.audio_renderer = audio
    result = generator(command('podcast'), replace(context(), is_cancel_requested=lambda: canceled[0]))
    assert result['canceled']
    assert not client.get('/api/personal-studio').json()['resources']


def test_real_audio_concatenation(tmp_path, monkeypatch):
    from app.services import classroom_narration
    async def narration(*, action, audio_dir):
        path = audio_dir / f'clip-{len(list(audio_dir.glob("clip-*.mp3")))}.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.3', '-y', str(path)], check=True)
        return path
    monkeypatch.setattr(classroom_narration, 'narration_audio', narration)
    asyncio.run(render_podcast(podcast(), tmp_path, context()))
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(tmp_path / 'podcast.mp3')], check=True, capture_output=True, text=True)
    assert float(json.loads(result.stdout)['format']['duration']) >= .6


@pytest.mark.parametrize('kind', ['lesson_plan', 'blog'])
def test_retired_generation_is_rejected_but_old_resources_remain_readable(setup, kind):
    client, manager, _, _ = setup
    response = client.post('/api/personal-studio/generate', json={'course_id': 'course', 'chapter_id': 'variables', 'request_id': 'retired', 'title': '旧工具', 'resource_type': kind})
    assert response.status_code == 422
    assert manager.save_generated_material(namespace('alice'), kind, 'legacy', {'title': '旧资料', 'content': '保留正文', 'studio_complete': True}, owner_user_id='alice', visibility='private')
    assert client.get(f'/api/personal-studio/resources/{kind}/legacy').json()['content'] == '保留正文'


def test_choices_can_rejoin_before_later_branching():
    data = scenario()
    data['scenes'][0]['choices'][1]['next_id'] = 'measure'
    assert Scenario.model_validate(data).start_id == 'start'


def test_generation_repair_receives_specific_validation_feedback(setup):
    _, manager, _, _ = setup
    calls = []
    class RepairModel:
        def chat(self, **kwargs):
            calls.append(copy.deepcopy(kwargs))
            return json.dumps({'title': 'incomplete'} if len(calls) == 1 else scenario(), ensure_ascii=False)
    result = StudioLearningResourceGenerator(manager, model_factory=lambda owner: RepairModel())(command(), context())
    assert result['saved']
    assert '结构检查发现' in calls[1]['messages'][-1]['content']
    assert calls[1]['messages'][-2]['role'] == 'assistant'


def test_manual_retry_new_task_reuses_its_owners_podcast_draft(setup):
    _, manager, _, _ = setup
    model = Model(podcast())
    async def failed(*args): raise RuntimeError('temporary audio failure')
    generator = StudioLearningResourceGenerator(manager, model_factory=lambda owner: model, audio_renderer=failed)
    with pytest.raises(DurableTaskExecutionError):
        generator(command('podcast'), context())
    async def audio(content, folder, ctx):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'podcast.mp3').write_bytes(b'ID3recovered')
    generator.audio_renderer = audio
    handler = PersonalStudioTaskHandler(manager=manager, learning_factory=FakeLearning, learning_generator=generator)
    result = handler({**command('podcast'), 'material_id': 'task-1'}, context(task='retry-task'))
    assert result['saved'] and len(model.calls) == 1
    assert read('alice', 'podcast', 'retry-task', manager)['source_job_id'] == 'retry-task'


@pytest.mark.parametrize('kind,settings', [
    ('podcast', {'topic': '赋值与复制', 'duration_minutes': 8, 'focus': '以购物清单类比共享对象'}),
    ('scenario', {'topic': '赋值与复制', 'difficulty': 'hard', 'setting': '你负责排查多人协作时的数据串改'}),
])
def test_every_visible_learning_resource_setting_reaches_model(setup, kind, settings):
    _, manager, _, _ = setup
    model = Model(podcast() if kind == 'podcast' else scenario())
    async def audio(content, folder, ctx):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'podcast.mp3').write_bytes(b'ID3test')
    generator = StudioLearningResourceGenerator(manager, model_factory=lambda owner: model, audio_renderer=audio)
    request = command(kind)
    request['config'].update(settings)
    result = generator(request, context())
    assert result['saved']
    messages = model.calls[0]['messages']
    assert json.loads(messages[1]['content'])['settings'] == settings
    if kind == 'podcast':
        assert '目标 8 分钟' in messages[0]['content']
        assert '2400 个中文字' in messages[0]['content']
