import asyncio
import hashlib
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from edu_deeptutor.api import create_app, Settings
from edu_deeptutor.contracts import GenerateRequest
from edu_deeptutor.runtime import ExamTurnEngine, prepare_sources, reserve_request, SubmissionConflict


def model(name):
    return {'model': name, 'base_url': 'http://127.0.0.1:1/v1', 'api_key': 'PRIVATE_' + name, 'api_format': 'openai_chat'}


def test_request_model_is_scoped_through_real_sdk_and_not_persisted(monkeypatch):
    from deeptutor.core.stream import StreamEvent, StreamEventType
    from deeptutor.services.session.turns.title_service import SessionTitleService
    captured = {}
    class Engine:
        async def execute(self, context):
            from deeptutor.services.llm.config import get_llm_config
            config = get_llm_config()
            await asyncio.sleep(0.02)
            assert get_llm_config().model == config.model
            assert config.edu_text_model["model"] == config.model + "-review"
            captured[context.user_message.split("\n\n")[0]] = (config.model, context.allowed_builtin_tools)
            assert len(context.attachments) == 1
            yield StreamEvent(type=StreamEventType.CONTENT, content='question', source='deep_question')
    async def no_title(*args, **kwargs): pass
    monkeypatch.setattr(SessionTitleService, '_maybe_generate_session_title', no_title)
    with TestClient(create_app(settings=Settings(token='long-test-token-with-32-characters'))) as client:
        gateway = client.app.state.gateway
        gateway.app.container.runtime_registry.turn_engine = ExamTurnEngine(Engine())
        async def exercise():
            from deeptutor.services.session import get_session_store
            async def one(owner):
                message = owner + '-' + uuid4().hex
                body = GenerateRequest(request_id=uuid4(), requirement=message, runtime_model=model(owner), runtime_text_model=model(owner + "-review"),
                    parsed_sources=[{'document_id': 'context', 'filename': 'context.md', 'source_hash': 'a' * 64,
                        'parser': 'text', 'role': 'context', 'content': 'Illustrated context', 'images': {
                            'pixel.png': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lWQAAAAASUVORK5CYII='}}])
                payload = body.upstream_payload(frozenset())
                immutable = json.dumps(payload, sort_keys=True)
                remote = await gateway.start(owner, payload)
                assert json.dumps(payload, sort_keys=True) == immutable
                events = [e async for e in gateway.events(owner, remote['turn_id'], 0)]
                assert any(e['type'] == 'done' for e in events)
                # A live process keeps its verified startup revision even if deployment files change.
                monkeypatch.setattr('edu_deeptutor.runtime._migration_revision', lambda: 'next-deployment-revision')
                assert (await gateway.start(owner, payload))['turn_id'] == remote['turn_id']
                with gateway.owner_scope(owner):
                    messages = await get_session_store().get_messages(remote['session_id'])
                    assert 'PRIVATE_' not in json.dumps(messages)
                assert await gateway.get('different-owner', remote['turn_id']) is None
                assert captured[message] == (owner, ['read_source'])
            await asyncio.gather(one('model-alice'), one('model-bob'))
        client.portal.call(exercise)


def test_parsed_paper_is_byte_equivalent_to_existing_extractor_input(tmp_path, monkeypatch):
    from deeptutor.tools.question.question_extractor import load_parsed_paper
    monkeypatch.setenv('DEEPTUTOR_HOME', str(tmp_path))
    content = '1. Choice: quick sort uses a pivot.\n2. Fill: merge sort complexity ____.'
    source = {'document_id': 'doc', 'source_hash': 'a'*64, 'filename': 'paper.pdf', 'parser': 'mineru-cloud',
              'role': 'template', 'content': content, 'content_list': [{'type': 'text', 'text': content, 'page_idx': 0}], 'images': {}}
    payload = prepare_sources('alice', str(uuid4()), [source], {'config': {}, 'content': 'requirements'})
    from pathlib import Path
    markdown, layout, images = load_parsed_paper(Path(payload['config']['paper_path']))
    assert markdown == content and layout == source['content_list']
    assert payload['content'] == 'requirements'


def test_submission_identity_includes_model_without_persisting_secret(tmp_path, monkeypatch):
    monkeypatch.setenv('DEEPTUTOR_HOME', str(tmp_path))
    reserve_request('alice', 'req', 'hash-1')
    reserve_request('alice', 'req', 'hash-1')
    with pytest.raises(SubmissionConflict): reserve_request('alice', 'req', 'hash-2')
    reserve_request('bob', 'req', 'hash-2')


def test_source_asset_paths_and_dual_model_selection_are_rejected():
    with pytest.raises(ValueError):
        GenerateRequest(request_id=uuid4(), requirement='x', runtime_model=model('a'),
                        model_selection={'profile_id': 'p', 'model_id': 'm'})
    with pytest.raises(ValueError):
        GenerateRequest(request_id=uuid4(), requirement='x', parsed_sources=[{'document_id': 'd', 'filename': 'p.pdf',
            'source_hash': 'a'*64, 'parser': 'mineru', 'content': 'x', 'images': {'../outside': 'eA=='}}])


def test_orphaned_turn_after_service_restart_fails_explicitly():
    with TestClient(create_app(settings=Settings(token='restart-test-token-with-32-characters'))) as client:
        gateway = client.app.state.gateway
        async def orphan():
            from deeptutor.services.session import get_session_store
            from deeptutor.runtime.coordination import MemoryCoordinator
            owner = 'restart-' + uuid4().hex
            with gateway.owner_scope(owner):
                store = get_session_store()
                session = await store.create_session()
                turn = await store.begin_turn(session['id'], turn_id='lost-' + uuid4().hex)
            status = await gateway.get(owner, turn['id'])
            assert status['status'] == 'failed'
            events = [e async for e in gateway.events(owner, turn['id'], 0)]
            assert any(e['type'] == 'done' and e['metadata'].get('status') == 'failed' for e in events)
        client.portal.call(orphan)
