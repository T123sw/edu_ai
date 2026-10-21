from __future__ import annotations
import hashlib
from contextlib import contextmanager
import time
from sqlalchemy import select, update, or_, and_
from sqlalchemy.exc import IntegrityError
from app.database.session import database_session
from .db_models import PblExercise, PblWorkspace, PblRun
from .schemas import Workspace, WorkspacePatch, RunRecord, ExerciseArtifact, ALGORITHM_PATH, TEMPLATE_VERSION
from .contracts import hash_code
from .project_schemas import parse_artifact, ProjectCheckRequest, ProjectRun, hash_files, PROJECT_TEMPLATE

from .runtime_config import MULTI_TEMPLATE, validate_files

class NotFound(LookupError): pass
class WorkspaceConflict(ValueError): pass
class StaleGeneration(WorkspaceConflict): pass

class PblRepository:
    def __init__(self, *, engine=None, lease_context=None):
        self.engine, self.lease_context = engine, lease_context

    def session(self):
        return database_session(engine=self.engine)

    @staticmethod
    def _owned(session, owner, exercise_id):
        row=session.scalar(select(PblExercise).where(PblExercise.id==exercise_id,PblExercise.owner==owner))
        if row is None: raise NotFound('练习不存在或无权访问')
        return row

    def get_owned(self, owner, exercise_id):
        with self.session() as session:
            row=self._owned(session,owner,exercise_id)
            session.expunge(row)
            return row

    def create_or_get(self, owner, request_id, topic):
        identifier='pbl_'+hashlib.sha256(f'{owner}:{request_id}'.encode()).hexdigest()[:32]
        try:
            with self.session() as session:
                row=session.get(PblExercise,identifier)
                if row is None:
                    now=time.time()
                    row=PblExercise(id=identifier,owner=owner,request_id=str(request_id),topic=topic,
                        current_job_id=identifier,created_at=now,updated_at=now)
                    session.add(row)
                    session.flush()
                if row.topic!=topic: raise WorkspaceConflict('相同请求编号不能用于不同主题')
        except IntegrityError:
            pass  # Concurrent insert: the unique key identifies the same request.
        row=self.get_owned(owner,identifier)
        if row.topic!=topic: raise WorkspaceConflict('相同请求编号不能用于不同主题')
        return row

    @contextmanager
    def creation_lock(self, owner, exercise_id):
        # Serializes cross-store enqueue reconciliation for a request on PostgreSQL.
        with self.session() as session:
            row=session.scalar(select(PblExercise).where(PblExercise.id==exercise_id,
                PblExercise.owner==owner).with_for_update())
            if row is None: raise NotFound('练习不存在或无权访问')
            yield row

    def list_owned(self, owner, *, cursor=None, limit=50):
        with self.session() as session:
            query=select(PblExercise).where(PblExercise.owner==owner)
            if cursor: query=query.where(PblExercise.id>cursor)
            rows=list(session.scalars(query.order_by(PblExercise.id).limit(limit)))
            for row in rows: session.expunge(row)
            return rows

    @staticmethod
    def _ready(row):
        if not row.artifact_public: raise WorkspaceConflict('练习尚未生成完成')
        return parse_artifact(row.artifact_public)

    @staticmethod
    def _workspace(row):
        return Workspace(exerciseId=row.exercise_id,artifactVersion=row.artifact_version,
            revision=row.revision,files=row.files,activeTaskId=row.active_task_id,
            customInputText=row.custom_input_text,updatedAt=row.updated_at)

    def get_or_create_workspace(self, owner, exercise_id):
        try:
            with self.session() as session:
                artifact=self._ready(self._owned(session,owner,exercise_id))
                row=session.get(PblWorkspace,(owner,exercise_id))
                if row is None:
                    row=PblWorkspace(owner=owner,exercise_id=exercise_id,artifact_version=artifact.artifactVersion,
                        revision=0,files=artifact.starterFiles if artifact.schemaVersion==2 else {ALGORITHM_PATH:artifact.starterCode},active_task_id=artifact.tasks[0].id,
                        custom_input_text='[3,1,2]',updated_at=time.time())
                    session.add(row)
                    session.flush()
                return self._workspace(row)
        except IntegrityError:
            with self.session() as session:
                self._owned(session,owner,exercise_id)
                return self._workspace(session.get(PblWorkspace,(owner,exercise_id)))

    def save_workspace(self, owner, exercise_id, patch):
        patch=WorkspacePatch.model_validate(patch)
        payload=patch.model_dump(mode='json')
        self.get_or_create_workspace(owner,exercise_id)
        with self.session() as session:
            artifact=self._ready(self._owned(session,owner,exercise_id))
            if artifact.artifactVersion!=patch.artifactVersion: raise WorkspaceConflict('练习版本已变化')
            if artifact.schemaVersion != 2 and sum(len(v.encode()) for v in patch.files.values()) > 131072:
                raise ValueError('源码超过运行环境限制')
            expected_files=set(artifact.starterFiles) if artifact.schemaVersion==2 else {ALGORITHM_PATH}
            if set(patch.files)!=expected_files or patch.activeTaskId not in {task.id for task in artifact.tasks}: raise ValueError('工程文件或步骤不匹配')
            row=session.get(PblWorkspace,(owner,exercise_id))
            if row.last_mutation_id==str(patch.mutationId):
                if row.last_mutation_payload!=payload: raise WorkspaceConflict('保存编号内容不一致')
                return self._workspace(row)
            changed=session.execute(update(PblWorkspace).where(PblWorkspace.owner==owner,
                PblWorkspace.exercise_id==exercise_id,PblWorkspace.revision==patch.expectedRevision,
                PblWorkspace.artifact_version==patch.artifactVersion).values(
                revision=PblWorkspace.revision+1,files=patch.files,active_task_id=patch.activeTaskId,
                custom_input_text=patch.customInputText,last_mutation_id=str(patch.mutationId),
                last_mutation_payload=payload,updated_at=time.time()),execution_options={'synchronize_session':False})
            session.expire_all()
            row=session.get(PblWorkspace,(owner,exercise_id))
            if not changed.rowcount:
                if row.last_mutation_id==str(patch.mutationId) and row.last_mutation_payload==payload:
                    return self._workspace(row)
                raise WorkspaceConflict('工作区已在其他位置更新，请保留草稿并解决冲突')
            return self._workspace(row)

    def append_run(self, owner, exercise_id, payload):
        report=RunRecord.model_validate(payload)
        row=self.get_owned(owner,exercise_id)
        artifact=self._ready(row)
        if artifact.schemaVersion==2: raise ValueError('项目检查只能由服务端执行')
        if report.exerciseId!=exercise_id or report.artifactVersion!=artifact.artifactVersion or report.templateVersion!=artifact.templateVersion:
            raise WorkspaceConflict('运行版本不匹配')
        if hash_code(report.code)!=report.codeHash: raise ValueError('源码哈希不匹配')
        cases=[c.model_dump() for c in report.cases]
        ids=[c.id for c in report.cases]
        result_ids=[r.caseId for r in report.results]
        if not ids or len(set(ids))!=len(ids) or len(set(result_ids))!=len(result_ids) or not set(result_ids)<=set(ids):
            raise ValueError('运行用例集合不匹配')
        if report.mode=='check' and {c['id']:c for c in cases}!={c.id:c.model_dump() for c in artifact.testCases}:
            raise ValueError('完整检查必须使用练习全部用例')
        if report.mode=='sample' and len(cases)!=1: raise ValueError('试运行只接受一个输入')
        for case in report.cases:
            if case.expected!=sorted(case.input): raise ValueError('用例预期值无效')
        expected={c.id:c.expected for c in report.cases}
        if any(r.expected!=expected[r.caseId] for r in report.results): raise ValueError('报告预期值不匹配')
        if report.status=='passed' and (set(result_ids)!=set(ids) or any(r.status!='passed' or r.actual!=expected[r.caseId] or r.returnedSameReference is not False or r.inputAfter!=next(c.input for c in report.cases if c.id==r.caseId) for r in report.results)):
            raise ValueError('通过报告不完整或结果不匹配')
        body=report.model_dump(mode='json')
        try:
            with self.session() as session:
                existing=session.get(PblRun,(owner,exercise_id,str(report.runId)))
                if existing:
                    if existing.payload!=body: raise WorkspaceConflict('运行编号内容不一致')
                    return existing.payload
                session.add(PblRun(owner=owner,exercise_id=exercise_id,run_id=str(report.runId),payload=body,created_at=time.time()))
                session.flush()
        except IntegrityError:
            with self.session() as session:
                existing=session.get(PblRun,(owner,exercise_id,str(report.runId)))
                if not existing or existing.payload!=body: raise WorkspaceConflict('运行编号内容不一致')
        return body

    def list_runs(self, owner, exercise_id, *, cursor=None, limit=50):
        with self.session() as session:
            self._owned(session,owner,exercise_id)
            query=select(PblRun).where(PblRun.owner==owner,PblRun.exercise_id==exercise_id)
            if cursor:
                pivot=session.get(PblRun,(owner,exercise_id,cursor))
                if pivot is None: raise ValueError('分页游标无效')
                query=query.where(or_(PblRun.created_at<pivot.created_at,and_(PblRun.created_at==pivot.created_at,PblRun.run_id<pivot.run_id)))
            return [r.payload for r in session.scalars(query.order_by(PblRun.created_at.desc(),PblRun.run_id.desc()).limit(limit))]

    def _guard(self, session, job_id):
        context=self.lease_context
        if context is None: return  # Administrative/unit setup; runtime always injects its execution context.
        if context.task_id!=job_id or context.is_cancel_requested(): raise StaleGeneration('生成已取消或被替代')
        if session.bind.dialect.name=='postgresql':
            from app.database.models import DurableTaskModel
            task=session.scalar(select(DurableTaskModel).where(DurableTaskModel.task_id==job_id).with_for_update())
            now=time.time()
            if not task or task.owner_user_id!=context.owner_user_id or task.status!='leased' or task.cancel_requested or task.lease_owner!=context.lease_owner or task.attempt_count!=context.attempt_count or not task.lease_expires_at or task.lease_expires_at<=now or (task.deadline_at is not None and task.deadline_at<=now):
                raise StaleGeneration('生成租约已过期')
        elif context.is_lease_valid is None or not context.is_lease_valid():
            raise StaleGeneration('生成租约已过期')

    def claim_generation(self, owner, exercise_id, job_id, retry_of_job_id=None):
        with self.session() as session:
            self._guard(session,job_id)
            self._owned(session,owner,exercise_id)
            condition=PblExercise.current_job_id==job_id
            if retry_of_job_id: condition=or_(condition,PblExercise.current_job_id==retry_of_job_id)
            return bool(session.execute(update(PblExercise).where(PblExercise.id==exercise_id,PblExercise.owner==owner,
                condition,PblExercise.artifact_public.is_(None)).values(current_job_id=job_id,generation_state='generating',updated_at=time.time())).rowcount)

    def save_checkpoint(self, owner, exercise_id, job_id, payload):
        with self.session() as session:
            self._guard(session,job_id)
            self._owned(session,owner,exercise_id)
            changed=session.execute(update(PblExercise).where(PblExercise.id==exercise_id,PblExercise.owner==owner,
                PblExercise.current_job_id==job_id,PblExercise.artifact_public.is_(None)).values(checkpoint=payload,
                candidate_private=payload.get('candidate'),repair_count=payload.get('repair_count',0),
                generation_state=payload.get('stage','generating'),updated_at=time.time()))
            if not changed.rowcount: raise StaleGeneration('生成任务已被替代')

    def publish(self, owner, exercise_id, job_id, artifact, private_candidate, validation_report):
        artifact=parse_artifact(artifact)
        if artifact.exerciseId!=exercise_id or artifact.templateVersion not in {TEMPLATE_VERSION,PROJECT_TEMPLATE,MULTI_TEMPLATE} or not validation_report.get('passed') or validation_report.get('templateVersion')!=artifact.templateVersion:
            raise ValueError('发布验证不匹配')
        if artifact.schemaVersion==2:
            results=validation_report.get('results',[])
            if [r.get('caseId') for r in results]!=[c.id for c in artifact.checks] or any(r.get('status')!='passed' for r in results) or validation_report.get('validatedSteps')!=len(artifact.tasks):
                raise ValueError('项目发布缺少完整运行证据')
        with self.session() as session:
            self._guard(session,job_id)
            row=self._owned(session,owner,exercise_id)
            if row.current_job_id!=job_id: raise StaleGeneration('生成任务已被替代')
            if row.artifact_public:
                if row.artifact_public==artifact.model_dump(mode='json'): return
                raise StaleGeneration('练习已发布')
            changed=session.execute(update(PblExercise).where(PblExercise.id==exercise_id,PblExercise.owner==owner,
                PblExercise.current_job_id==job_id,PblExercise.artifact_public.is_(None)).values(
                artifact_public=artifact.model_dump(mode='json'),candidate_private=private_candidate,
                artifact_version=artifact.artifactVersion,template_version=artifact.templateVersion,
                validation_report=validation_report,generation_state='ready',updated_at=time.time()))
            if not changed.rowcount: raise StaleGeneration('生成任务已被替代')

    def project_check_input(self, owner, exercise_id, payload):
        request=ProjectCheckRequest.model_validate(payload)
        artifact=self._ready(self.get_owned(owner,exercise_id))
        if artifact.schemaVersion!=2 or request.artifactVersion!=artifact.artifactVersion:
            raise WorkspaceConflict('项目运行版本不匹配')
        validate_files(request.files,artifact.starterFiles)
        task=next((t for t in artifact.tasks if t.id==request.taskId),None)
        if task is None: raise ValueError('未知项目步骤')
        with self.session() as session:
            existing=session.get(PblRun,(owner,exercise_id,str(request.runId)))
            if existing:
                if not self._same_project_request(existing.payload,request): raise WorkspaceConflict('运行编号内容不一致')
                return request,[],existing.payload
        by_id={c.id:c.model_dump(exclude_none=True) for c in artifact.checks}
        return request,[by_id[cid] for cid in task.cumulativeCheckIds],None

    @staticmethod
    def _same_project_request(report,request):
        return (report.get('templateVersion') in {PROJECT_TEMPLATE,MULTI_TEMPLATE} and report.get('artifactVersion')==request.artifactVersion
            and report.get('taskId')==request.taskId and report.get('codeHash')==hash_files(request.files))

    def save_project_check(self, owner, exercise_id, payload, result):
        request,checks,existing=self.project_check_input(owner,exercise_id,payload)
        if existing: return existing
        results=result.get('results',[])
        if [r.get('caseId') for r in results]!=[c['id'] for c in checks]: raise ValueError('运行结果集合不完整')
        passed=all(r.get('status')=='passed' for r in results)
        if bool(result.get('passed'))!=passed: raise ValueError('运行状态不一致')
        artifact=self._ready(self.get_owned(owner,exercise_id))
        body=ProjectRun(runId=request.runId,exerciseId=exercise_id,artifactVersion=request.artifactVersion,templateVersion=artifact.templateVersion,
            taskId=request.taskId,codeHash=hash_files(request.files),status='passed' if passed else 'failed',
            results=results,durationMs=result['durationMs']).model_dump(mode='json')
        try:
            with self.session() as session:
                session.add(PblRun(owner=owner,exercise_id=exercise_id,run_id=str(request.runId),payload=body,created_at=time.time()))
                session.flush()
        except IntegrityError:
            with self.session() as session:
                existing=session.get(PblRun,(owner,exercise_id,str(request.runId)))
                if not existing or not self._same_project_request(existing.payload,request): raise WorkspaceConflict('运行编号内容不一致')
                return existing.payload
        return body
