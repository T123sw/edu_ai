"""Continue a live B generated material through the shared B/C SSE entry."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace


def main(evidence_dir):
    from core.config import Config
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    for key in ('USER', 'COURSE', 'COURSE_MEMBERSHIP', 'CONVERSATION', 'JOB', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE', 'LEARNING', 'TASK'):
        os.environ[key + '_PERSISTENCE_MODE'] = 'json'
    os.environ['DATABASE_URL'] = ''
    os.environ['PERSISTENCE_PROFILE'] = 'compatibility'
    evidence_dir = Path(evidence_dir)
    generated = json.loads((evidence_dir / 'live-context.json').read_text())['materials'][-1]['material']
    cid, mid = generated['course_id'], generated['material_id']
    matches = list(Path('/tmp').glob(f'b-context-live-*/course_storage_root/courses/{cid}/generated_materials/reports/{mid}.json'))
    # IDs are synthetic and unique to captured generation commands; no access
    # to the repository's configured production material store.
    if len(matches) != 1:
        raise RuntimeError('expected exactly one synthetic generated manifest')
    root = matches[0].parents[4]
    for attr in ('STORAGE_ROOT', 'COURSE_STORAGE_ROOT', 'CONVERSATIONS_FILE', 'COURSE_MEMBERSHIPS_FILE', 'USER_PROFILES_FILE', 'LESSON_PLANS_FILE', 'LEARNING_DB_PATH', 'RUNTIME_CONFIG_ROOT'):
        old = getattr(Config, attr)
        value = root.parent / 'bc-runtime' / (attr.lower() if attr.endswith('ROOT') else Path(old).name)
        setattr(Config, attr, value)
        os.environ[attr] = str(value)
    for key in ('TASKS_DB_PATH', 'AGENT_RUNS_DB_PATH'):
        os.environ[key] = str(root.parent / (key.lower() + '.db'))
    from core.course_storage import CourseStorageManager
    from core.conversation_storage import ConversationStorage
    from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
    from app.chat.application.knowledge_context import KnowledgeContextService
    from app.chat.application.reply_service_v2 import ReplyServiceV2
    from app.artifact_revision.service import ArtifactRevisionService
    from app.chat.agents.report_generation import get_fallback_llm
    manager = CourseStorageManager(root)
    conversations = ConversationStorage(root.parent / 'bc-conversations.json')
    owner = generated['owner_user_id']
    def authorize(request):
        if request.owner != owner or request.course_id != cid:
            raise PermissionError('synthetic workspace only')
    service = ReplyServiceV2(
        conversation_store=ConversationStoreAdapter(storage=conversations),
        course_storage_manager=manager,
        knowledge_context_service=KnowledgeContextService(course_storage=manager, conversation_storage=conversations, authorize=authorize),
        artifact_revision_service=ArtifactRevisionService(manager, get_fallback_llm()),
    )
    reference = {'artifact_id': mid, 'artifact_type': 'report', 'version_id': 'v1', 'source_course_id': cid}
    payload = SimpleNamespace(owner=owner, conversation_id='bc-live-verified', course_id=cid, scope_type='course', scope_id=None,
        question='修改刚生成的数组报告，只在报告最后增加一句“验收标记 B-C-20260907”，其余所有文字保持不变。', artifact_reference=reference)
    events = list(service.reply_stream(payload))
    result = next(event['payload'] for event in events if event['type'] == 'result')
    revised = manager.get_generated_material(cid, 'report', mid, owner_user_id=owner)
    evidence = {'request': vars(payload), 'result': result, 'scope_id': revised['scope_id'], 'version': revised['version'],
        'marker_present': 'B-C-20260907' in revised['content'], 'original_body_preserved': generated['content'].strip() in revised['content'],
        'event_types': [event['type'] for event in events]}
    (evidence_dir / 'live-bc-revision.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({key:value for key,value in evidence.items() if key not in {'request', 'result'}}, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
