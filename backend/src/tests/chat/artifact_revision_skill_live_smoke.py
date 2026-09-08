"""Explicit live read/edit smoke; synthetic material in isolated temporary storage."""
import json
import os
import sys
import tempfile
from pathlib import Path


def main(output_dir):
    from core.config import Config
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    root = Path(tempfile.mkdtemp(prefix='revision-skill-live-'))
    for key in ('USER', 'COURSE', 'COURSE_MEMBERSHIP', 'CONVERSATION', 'JOB', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE', 'LEARNING', 'TASK'):
        os.environ[key + '_PERSISTENCE_MODE'] = 'json'
    os.environ['PERSISTENCE_PROFILE'] = 'compatibility'
    os.environ['DATABASE_URL'] = ''
    for attr in ('STORAGE_ROOT', 'COURSE_STORAGE_ROOT', 'CONVERSATIONS_FILE', 'COURSE_MEMBERSHIPS_FILE', 'USER_PROFILES_FILE', 'LESSON_PLANS_FILE', 'LEARNING_DB_PATH', 'RUNTIME_CONFIG_ROOT'):
        old = getattr(Config, attr)
        value = root / attr.lower() if attr.endswith('ROOT') else root / Path(old).name
        setattr(Config, attr, value)
        os.environ[attr] = str(value)
    for key in ('TASKS_DB_PATH', 'AGENT_RUNS_DB_PATH', 'AGENT_MEMORY_DB_PATH'):
        os.environ[key] = str(root / (key.lower() + '.db'))
    from core.course_storage import CourseStorageManager
    from app.artifact_revision.service import ArtifactRevisionService, reference
    from app.chat.agents.report_generation import get_fallback_llm
    manager = CourseStorageManager(root / 'materials')
    owner, course, mid = 'skill-smoke-teacher', 'skill-smoke-course', 'linked-list-smoke'
    source = '# 链表的实现\n\n## 结构\n每个节点包含 data 和 next，head 指向首节点。\n\n## 插入\n头插时先让新节点 next 指向旧 head，再更新 head。\n\n## 遍历\n从 head 开始沿 next 访问，直到空指针。\n\n保留标记 SKILL-READ-20260907。'
    assert manager.save_generated_material(course, 'report', mid, {'title': '链表的实现', 'content': source}, owner_user_id=owner, visibility='private', scope_type='knowledge_point', scope_id='linked-list')
    service = ArtifactRevisionService(manager, get_fallback_llm())
    ref = reference(manager.get_generated_material(course, 'report', mid, owner_user_id=owner))
    assert ref['content_hash']
    def run(question, operation, pending=None):
        return service.run(owner_user_id=owner, conversation_id='skill-smoke', course_id=course, question=question, operation_id=operation, artifact_reference=ref, pending=pending)
    read = run('这个文档写的什么', 'read-1')
    version_after_read = manager.get_generated_material(course, 'report', mid, owner_user_id=owner)['version']
    edit = run('只在“插入”一节末尾增加一句“头插法的时间复杂度为 O(1)。”，其他文字完全保留。', 'edit-1')
    assert edit['status'] == 'preview', edit
    proposal = edit
    assert manager.get_generated_material(course, 'report', mid, owner_user_id=owner)['version'] == 1
    edit = run('保存当前修改稿。', 'edit-1', pending=proposal['pending'])
    current = manager.get_generated_material(course, 'report', mid, owner_user_id=owner)
    evidence = {'source': source, 'read': read, 'version_after_read': version_after_read, 'proposal': proposal, 'edit': edit, 'final_version': current['version'], 'final_content': current['content']}
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'live.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    assert read['status'] == 'answered', read
    assert version_after_read == 1
    assert edit['status'] == 'completed', edit
    assert current['version'] == 2
    assert '头插法的时间复杂度为 O(1)。' in current['content']
    assert current['content'].replace('头插法的时间复杂度为 O(1)。', '').replace('\n', '') == source.replace('\n', '')
    print(json.dumps({'read': read['status'], 'version_after_read': version_after_read, 'edit': edit['status'], 'final_version': current['version'], 'unrelated_content_preserved': True}))


if __name__ == '__main__':
    main(sys.argv[1])
