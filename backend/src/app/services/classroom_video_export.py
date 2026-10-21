"""Native HyperFrames exports; old records retain existing downloadable files."""
from __future__ import annotations
import json
import shutil
from typing import Any, Optional
from app.services.job_store import EduJob, JobKind, JobStatus, create_job, update_job
from core.course_storage import CourseStorageManager
from app.self_learning.hyperframes_context import native_content
from app.integrations.hyperframes.projects import ProjectStore

VIDEO_ARTIFACT_MEDIA_TYPES={'classroom.mp4':'video/mp4','classroom.srt':'application/x-subrip','timeline.json':'application/json'}


async def run_classroom_video_export_job(job, *, course_id, classroom_id, auth_token=None,
        current_user, course_storage_manager, **unused):
    material=course_storage_manager.get_generated_material(course_id,'classroom',classroom_id,
        owner_user_id=current_user['username'])
    content=native_content(material or {})
    if not content:
        raise ValueError('历史课堂仅保留已有导出，请重新生成 HyperFrames 课堂后导出')
    directory=course_storage_manager.get_classroom_video_dir(course_id,classroom_id)
    directory.mkdir(parents=True,exist_ok=True)
    store=ProjectStore()
    for kind,name in (('video','classroom.mp4'),('subtitles','classroom.srt')):
        shutil.copyfile(store.file(content['project'],content['exports'][kind]),directory/name)
    (directory/'timeline.json').write_text(json.dumps(content['timeline'],ensure_ascii=False))
    return update_job(job.edu_job_id,status=JobStatus.SUCCEEDED,step='completed',progress=100,
        message='原生课堂视频导出完成',result_ref={'course_id':course_id,'classroom_id':classroom_id,
        'version':material['version'],'project_digest':content['project']['digest'],
        'video_url':f'/api/courses/{course_id}/classrooms/{classroom_id}/video/classroom.mp4',
        'subtitle_url':f'/api/courses/{course_id}/classrooms/{classroom_id}/video/classroom.srt',
        'timeline_url':f'/api/courses/{course_id}/classrooms/{classroom_id}/video/timeline.json',
        'duration_ms':round(content['timeline']['duration']*1000),
        'scene_count':len(content['timeline']['segments'])}) or job


async def submit_classroom_video_export_job(
    *,
    course_id: str,
    classroom_id: str,
    auth_token: str,
    current_user: dict[str, Any],
    owner: Optional[str],
    course_storage_manager: CourseStorageManager,
    existing_job: Optional[EduJob] = None,
) -> EduJob:
    job = existing_job or create_job(
            kind=JobKind.RENDER_VIDEO,
            owner_user_id=owner,
            course_id=course_id,
            input_summary={
                "title": f"课堂视频 · {classroom_id}",
                "resource_type": "classroom_video",
                "classroom_id": classroom_id,
                "source": "classroom-player",
            },
        )

    from app.services.platform_task_handlers import enqueue_platform_task

    return enqueue_platform_task(
        job=job,
        workflow_type="classroom_video_export",
        command={
            "course_id": course_id,
            "classroom_id": classroom_id,
            "owner_role": str(current_user.get("role") or "teacher"),
        },
    )
