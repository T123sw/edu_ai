"""Explicit live smoke: real v2 Agent + report worker, temporary synthetic data.

Run from backend/src, with an output directory argument. Durable submission is
captured and its production handler run in-process; no shared worker/database.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


def main(output_dir):
    from core.config import Config
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    root = Path(tempfile.mkdtemp(prefix='b-context-live-'))
    for key in ('USER', 'COURSE', 'COURSE_MEMBERSHIP', 'CONVERSATION', 'JOB', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE', 'LEARNING', 'TASK'):
        os.environ[key + '_PERSISTENCE_MODE'] = 'json'
    os.environ['PERSISTENCE_PROFILE'] = 'compatibility'
    os.environ['DATABASE_URL'] = ''
    for attr in ('STORAGE_ROOT', 'COURSE_STORAGE_ROOT', 'CONVERSATIONS_FILE', 'COURSE_MEMBERSHIPS_FILE', 'USER_PROFILES_FILE', 'LESSON_PLANS_FILE', 'LEARNING_DB_PATH', 'RUNTIME_CONFIG_ROOT'):
        old = getattr(Config, attr)
        value = root / attr.lower() if attr.endswith('ROOT') else root / Path(old).name
        setattr(Config, attr, value)
        os.environ[attr] = str(value)
    for key in ('TASKS_DB_PATH', 'AGENT_RUNS_DB_PATH'):
        os.environ[key] = str(root / (key.lower() + '.db'))
    Config.USE_REACT_AGENT = True
    Config.REACT_MAX_STEPS = 8
    Config.REACT_TIMEOUT_SECONDS = 100

    import app.chat.application.knowledge_context as knowledge
    from app.chat.application.reply_service_v2 import build_default_reply_service_v2
    from core.course_storage import storage_manager
    from app.services.generation_task_handlers import GenerationTaskHandler
    from app.services.generation_command import generation_command_service

    owner, course = 'b-context-smoke-teacher', 'b-context-smoke-course'
    storage_manager.save_course_info(course, {'id': course, 'title': '数据结构'})
    storage_manager.save_knowledge_graph(course, {'root': {'id': 'root', 'label': '数据结构', 'children': [
        {'id': 'array', 'label': '数组'}, {'id': 'list', 'label': '链表'},
        {'id': 'ch1', 'label': '章节一', 'children': [{'id': 't1', 'label': '遍历'}]},
        {'id': 'ch2', 'label': '章节二', 'children': [{'id': 't2', 'label': '遍历'}]},
    ]}})
    def authorize(request):
        if request.owner != owner or request.course_id != course:
            raise PermissionError('synthetic workspace only')
    knowledge.authorize_workspace = authorize
    service = build_default_reply_service_v2()
    service.knowledge_context_service.authorize = authorize
    service.memory_writer = None
    submitted = []
    def submit(command, **kwargs):
        submitted.append(command)
        return SimpleNamespace(edu_job_id=f'job_b_context_{len(submitted)}')
    generation_command_service.submit = submit
    evidence = {'model': Config.get_agent_model().get('model_name'), 'cases': [], 'worker_mode': 'production handler invoked in-process after captured submission'}
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)

    def turn(question, cid, scope_id=None):
        before = len(submitted)
        events = list(service.reply_stream(SimpleNamespace(question=question, conversation_id=cid, owner=owner, course_id=course,
            scope_type='knowledge_point' if scope_id else 'course', scope_id=scope_id, source_mode='none', allow_rag=False, allow_web=False, allow_image_search=False)))
        result = next((event.get('payload') for event in events if event.get('type') == 'result'), {})
        entry = {'question': question, 'scope_id': scope_id, 'result': result, 'new_generation_calls': len(submitted)-before}
        evidence['cases'].append(entry)
        (output / 'live-context.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
        print(json.dumps({'question': question, 'action': result.get('action'), 'new_generation_calls': len(submitted)-before}, ensure_ascii=False), flush=True)
        return result

    question = '为当前课程生成一份简短报告，约300字，不配图、不联网。请直接生成。'
    turn(question, 'b-live-resolved', 'array')
    if not submitted:
        turn('确认生成', 'b-live-resolved', 'array')
    turn(question, 'b-live-clarify')
    before_resume = len(submitted)
    turn('数组', 'b-live-clarify')
    if len(submitted) == before_resume:
        turn('确认生成', 'b-live-clarify', 'array')
    turn('为遍历生成报告', 'b-live-duplicate', 'array')
    handler = GenerationTaskHandler(course_storage_manager=storage_manager)
    for index, command in enumerate(submitted[:2]):
        context = SimpleNamespace(task_id=f'job_b_context_{index+1}', course_id=course, owner_user_id=owner,
            config_snapshot_id=command.config_snapshot_id, is_cancel_requested=lambda: False, progress=lambda *args: None)
        result = handler.handle(command.model_dump(mode='json'), context)
        material = storage_manager.get_generated_material(course, command.resource_type, command.material_id, owner_user_id=owner)
        evidence.setdefault('materials', []).append({'command': command.model_dump(mode='json'), 'result_ref': result.get('result_ref'), 'material': material})
        (output / 'live-context.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
        print(json.dumps({'saved': result.get('saved'), 'scope_id': (material or {}).get('scope_id'), 'content_length': len(str((material or {}).get('content', '')))}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
