"""Native generation for classroom Studio/Harness durable jobs."""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from app.integrations.hyperframes.generation import generate_classroom
from app.integrations.hyperframes.projects import digest_bytes
from app.services.classroom_service import _build_research_context
from app.services.job_store import update_job, JobStatus


class JobCheckpoint:
    """Atomic durable phase state, scoped by opaque job identity."""
    def __init__(self, owner, job):
        root = Path(os.environ.get('COURSE_STORAGE_ROOT','data/course_storage')) / 'hyperframes' / 'checkpoints'
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / (digest_bytes((owner+'\0'+job).encode())+'.json')
    def load_generation_state(self):
        return json.loads(self.path.read_text()) if self.path.is_file() else None
    def save_generation_state(self,value):
        temporary = self.path.with_suffix('.'+uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False))
        temporary.replace(self.path)


def generate_and_persist(command, context, manager, source, requirement):
    from app.self_learning.service import gateway
    course = str(command.get('course_id') or context.course_id or '')
    owner = context.owner_user_id
    context.progress(3,'research','正在准备课程资料')
    research = asyncio.run(_build_research_context(course_storage_manager=manager,course_id=course,
        requirement=requirement,web_research_context=command.get('web_research_context'),
        rag_top_k=int(command.get('rag_top_k') or 5),rag_system=None,resolved_source=source,
        include_knowledge_graph=not bool((command.get('material_metadata') or {}).get('harness_config'))))
    from app.integrations.hyperframes.assets import selected_media
    visual_snapshot = dict(command.get('visual_assets') or {})
    media_files, visual_snapshot = selected_media(visual_snapshot, owner=owner)
    rid = str(command.get('material_id') or 'classroom_'+context.task_id).strip()
    payload = SimpleNamespace(title=command.get('topic') or requirement.split('\n')[0], focus=requirement,
        research_context=research or '', pdf_content=command.get('pdf_content'), visual_assets=visual_snapshot, audience=command.get('audience',''), objectives=command.get('objectives',[]),
        duration_minutes=command.get('duration_minutes'), video_preferences=command.get('video_preferences'),
        scene_count=command.get('scene_count'), teaching_style=command.get('teaching_style'),
        classroom_options={key:command[key] for key in ('voice','enable_tts','include_visuals') if command.get(key) is not None})
    artifact = {'resource_id':rid,'spec_digest':digest_bytes(json.dumps(command,sort_keys=True,ensure_ascii=False).encode())}
    result = generate_classroom(payload,gateway=gateway(owner),context=context,artifact=artifact,
        checkpoint=JobCheckpoint(owner,context.task_id),media_files=media_files)
    if context.is_cancel_requested(): raise RuntimeError('CANCELED')
    metadata = dict(command.get('material_metadata') or {})
    metadata.pop('_tts_options',None)
    content = result['content']
    data = {**metadata,**result,**content,'owner':owner,'scenes_count':len(content['timeline']['segments'])}
    context.progress(95,'persisting','正在保存原生课堂工程')
    saved = manager.save_generated_material(course,'classroom',rid,data,scope_type=command.get('scope_type') or 'course',
        scope_id=command.get('scope_id'),owner_user_id=owner,source_snapshot={**source.to_snapshot(), 'visual_assets':visual_snapshot},source_job_id=context.task_id,
        visibility='course' if metadata and (metadata.get('origin_type')=='standard' or not metadata.get('harness_config')) else 'private')
    if not saved: raise RuntimeError('HYPERFRAMES_PERSIST_FAILED')
    stored = manager.get_generated_material(course,'classroom',rid,owner_user_id=owner)
    if not stored: raise RuntimeError('HYPERFRAMES_READBACK_FAILED')
    update_job(context.task_id,status=JobStatus.SUCCEEDED,progress=100,step='completed',message='课堂已生成',
        result_ref={'resource_type':'course_material','material_type':'classroom','material_id':rid,'classroom_id':rid,
            'course_id':course,'version':stored['version'],'content_hash':stored.get('content_hash'),
            'scenes_count':len(content['timeline']['segments'])})
