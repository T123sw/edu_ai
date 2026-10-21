from pathlib import Path
import json,os,shutil
from datetime import datetime,timezone
from core.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database.models import Course,CourseMembership,CourseObjective,User,PreparationArtifact,PreparedManifestVersion,PreparedCoursePointer
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from app.integrations.hyperframes.projects import ProjectStore
from app.integrations.hyperframes.workflow_import import import_project
from app.course_preparation.manifest import CourseManifest
from app.course_preparation.tool_registry import digest
root=Path('/home/zxqs_ep/data/main-review/hyperframes-teaching-brief-20261019')
ev=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-19-hyperframes-teaching-brief')
course_id='bubble-sort-five-minute-20261019';title='冒泡排序 Python 实现 · 五分钟视频验证'
lesson='写出并运行冒泡排序代码，分析复杂度与适用场景'
description='新版教学简报与 HyperFrames general-video 的独立技术验证样片，约 4 分 55 秒。本课程仅展示本次已生成视频，不代表整门课程的报告和习题验收。'
engine=create_engine(os.environ['DATABASE_URL']);store=ProjectStore();repo=PostgresMaterialRepository(engine)
with Session(engine) as db:
 source=db.get(PreparationArtifact,'artifact_7aee94c4550f6c900e45e64445f02ae6');actor=db.get(User,source.owner_user_id)
 assert actor.username=='teacher' and not actor.is_disabled
 owner_id,owner,source_id=actor.user_id,actor.username,source.preparation_id
 assert db.get(Course,course_id) is None,'Course already exists; inspect instead of overwrite'
workspace=next((root/'workflows').iterdir());project=workspace/'videos/bubble-sort-python'
(project/'exports').mkdir(exist_ok=True)
shutil.copy2(workspace/'.host/teaching-brief.json',project/'exports/teaching-brief.json')
body=import_project(project,project/'renders/video.mp4',title=lesson,project_id='hf_five_minute_demo_20261019',store=store)
assert len(body['timeline']['segments'])==9 and all(s['narration'] for s in body['timeline']['segments'])
rid='hf_five_minute_demo_20261019';node='bubble_python';oid='bubble_python_objective';now=datetime.now(timezone.utc).isoformat()
content_hash=digest({'content':body,'title':lesson,'artifact_type':'classroom'})
material={'course_id':course_id,'material_type':'classroom','material_id':rid,'title':lesson,'content':body,**body,'version':1,'content_hash':content_hash,'visibility':'private','origin_type':'personal','owner_user_id':owner,'created_by':owner,'scope_type':'knowledge_point','scope_id':node,'created_at':now,'updated_at':now,'learning_course_resource':True,'status':'ready','scenes_count':9,'import_provenance':{'kind':'teaching_brief_validation','source_preparation_id':source_id,'source_artifact_id':source.artifact_id,'generated_result':str(root/'result.json')}}
objective='运行 Python 冒泡排序，解释循环边界、提前终止和复杂度。'
manifest=CourseManifest.model_validate({'manifest_id':'manifest_hf_five_minute_20261019','course_id':course_id,'version':1,'route_version':1,'goal':description,'audience':'算法初学者','estimated_minutes':5,'nodes':[{'node_id':node,'title':lesson,'order':1,'objectives':[{'objective_id':oid,'text':objective}],'prerequisite_node_ids':[],'estimated_minutes':5,'resources':[{'resource_id':rid,'resource_type':'classroom','version':1,'content_sha256':content_hash,'purpose':'查看新版约五分钟讲解视频。','order':1,'objective_ids':[oid],'objective_coverage':'planned'}]}],'quality_report_id':'technical_preview_validation_20261019','limitations':['独立视频技术验证，未重新执行整门课程调研、报告与习题生成。','已验证媒体解码、时间轴和讲稿导入；未做完整教学事实审校。'],'created_by_preparation_id':source_id}).model_dump(mode='json')
with Session(engine) as db,db.begin():
 assert db.get(Course,course_id) is None
 info={'id':course_id,'title':title,'description':description,'created_by':owner,'created_at':now,'updated_at':now,'self_learning':True,'prepared_course':True,'demo_course':True,'audience':'算法初学者','language':'中文'}
 db.add(Course(course_id=course_id,title=title,description=description,created_by=owner_id,icon='menu_book',color='#3556d8',raw_payload=info));db.flush()
 db.add(CourseMembership(course_id=course_id,user_id=owner_id,role='owner',added_by=owner_id))
 db.add(CourseObjective(course_id=course_id,position=0,objective=objective))
 repo.upsert(material,session=db);db.flush()
 db.add(PreparedManifestVersion(owner_user_id=owner_id,course_id=course_id,version=1,manifest_id=manifest['manifest_id'],preparation_id=source_id,payload=manifest,content_digest=digest(manifest)))
 db.add(PreparedCoursePointer(owner_user_id=owner_id,course_id=course_id,version=1))
(ev/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
record={'course_id':course_id,'title':title,'owner':owner,'path':f'/#/classroom/{course_id}','imported_at':now,'project':body['project'],'duration':body['timeline']['duration'],'segments':len(body['timeline']['segments']),'original_task_modified':False,'source_preparation_id':source_id}
(ev/'import.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps(record,ensure_ascii=False))
