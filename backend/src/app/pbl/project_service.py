"""Private, resumable Skill pipeline; publication requires real cumulative execution."""
import asyncio
import hashlib
import json
from app.services.durable_task_handlers import DurableTaskExecutionError
from .project_workflow import load_project_skill, validate_step_unit
from .project_schemas import (ProjectArtifact, STARTER_FILES, PROJECT_TEMPLATE, validate_runtime_plan, validate_planned_checks, hash_files)
from .project_generator import generate_project_phase, StepCandidate, StepImplementation, StepAcceptance, InvalidProjectOutput
from .validation import RuntimeUnavailable
from .runtime_config import MULTI_TEMPLATE, runtime_for, starter_files, validate_files

async def generate_project(command, context, repository):
    from .service import guarded_operation, check_context, result_ref
    from app.services.job_store import get_job
    from .project_validation import check_project
    owner,identifier=context.owner_user_id,command['exercise_id']
    versions={phase:load_project_skill(phase)['version'] for phase in ('plan','review_plan','build_step','repair_step','build_checks','repair_checks','validate','publish')}
    checkpoint=dict(repository.get_owned(owner,identifier).checkpoint or {})
    if checkpoint and (checkpoint.get('skillVersions')!=versions or checkpoint.get('templateVersion') not in {PROJECT_TEMPLATE,MULTI_TEMPLATE}):
        checkpoint={}  # Changed Skill invalidates all saved execution evidence.
    plan=checkpoint.get('plan')
    completed=checkpoint.get('completed',[])
    if plan:
        try:
            validate_runtime_plan(plan)
            expected_hash=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if checkpoint.get('planHash')!=expected_hash: raise ValueError('检查点计划哈希不匹配')
            if len(completed)>len(plan['steps']): raise ValueError('检查点步骤过多')
            for index,item in enumerate(completed):
                candidate=StepCandidate.model_validate(item['candidate'])
                validate_step_unit(plan,candidate.unit.model_dump())
                if item.get('referenceHash')!=hash_files(candidate.referenceFiles) or item.get('faultyHash')!=hash_files(candidate.faultyFiles):
                    raise ValueError('检查点源码哈希不匹配')
                if candidate.unit.stepId!=plan['steps'][index]['id'] or [c.id for c in candidate.checks]!=plan['steps'][index]['newCheckIds'] or not item.get('validated'):
                    raise ValueError('检查点步骤无效')
        except (ValueError,TypeError,KeyError): plan=None; completed=[]; checkpoint={}
    review=checkpoint.get('review')
    repairs=dict(checkpoint.get('repairs') or {})
    repair_totals=dict(checkpoint.get('repairTotals') or repairs)
    job=get_job(context.task_id)
    # Worker/lease recovery keeps its budget. Only an explicit retry job grants
    # a fresh bounded budget; persist its identity before any model operation.
    if (job and job.retry_of_job_id and checkpoint
            and checkpoint.get('generationJobId',job.retry_of_job_id)==job.retry_of_job_id):
        repairs={}
    pending=checkpoint.get('pending')
    issues=checkpoint.get('issues') or []
    prior_candidate=checkpoint.get('lastCandidate')
    previous_check_report=checkpoint.get('previousCheckReport')
    failure_context=checkpoint.get('failureContext')
    if not failure_context and plan and len(completed)<len(plan['steps']):
        failed_step=plan['steps'][len(completed)]['id']
        if (checkpoint.get('repairs') or {}).get(failed_step):
            failure_context={'stepId':failed_step,'issues':issues,'priorCandidate':prior_candidate,'previousCheckReport':previous_check_report}
    def save(stage, **extra):
        check_context(context)
        repository.save_checkpoint(owner,identifier,context.task_id,{
            'kind':'sandpack_project' if plan and plan.get('runtime') else 'react_app','stage':stage,'skillVersions':versions,'templateVersion':MULTI_TEMPLATE if plan and plan.get('runtime') else PROJECT_TEMPLATE,'plan':plan,
            'planHash':hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'repairs':repairs,'repairTotals':repair_totals,'generationJobId':context.task_id,'pending':pending,
            'review':review,'completed':completed,'issues':issues,'lastCandidate':prior_candidate,'previousCheckReport':previous_check_report,
            'failureContext':failure_context,'proposedPlan':checkpoint.get('proposedPlan'),**extra})
    save('resuming')
    async def model(phase,data):
        try: return await guarded_operation(generate_project_phase(owner,command.get('runtime_config_snapshot') or {},phase,data),context)
        except (ValueError,TypeError): raise
        except DurableTaskExecutionError: raise
        except Exception:
            save('model_failed')
            raise DurableTaskExecutionError('PBL_MODEL_UNAVAILABLE','模型服务暂不可用，请稍后重试') from None
    async def execute(files,checks):
        try:
            validate_files(files,plan['editableFiles'])
            runtime=runtime_for(plan)
            report=await guarded_operation(asyncio.to_thread(check_project,files,checks,**({'runtime':runtime} if runtime else {})),context)
            results=report.get('results',[])
            if [r.get('caseId') for r in results]!=[c['id'] for c in checks] or any(r.get('status') not in {'passed','failed'} for r in results) or bool(report.get('passed'))!=all(r['status']=='passed' for r in results):
                raise RuntimeUnavailable('检查报告不完整')
            return report
        except RuntimeUnavailable:
            save('runtime_failed')
            raise DurableTaskExecutionError('PBL_RUNTIME_UNAVAILABLE','浏览器检查环境暂不可用，请稍后重试') from None
    if plan is None:
        issues=checkpoint.get('issues') or []
        proposed=checkpoint.get('proposedPlan')
        for attempt in range(repairs.get('plan',0),3):
            context.progress(10,'pbl_plan','正在拆解项目目标与步骤')
            save('planning',repair_count=attempt,issues=issues,proposedPlan=proposed)
            try:
                proposed=await model('plan',{'topic':command['topic'],'issues':issues,'priorPlan':proposed})
                plan=validate_runtime_plan(proposed,require_check_contract=True)['plan']
                break
            except (ValueError,TypeError) as exc:
                if isinstance(exc,InvalidProjectOutput): proposed=exc.raw
                issues=[str(exc)[:2000]]; plan=None; repairs['plan']=attempt+1
                repair_totals['plan']=repair_totals.get('plan',0)+1
        if plan is None:
            save('failed',issues=issues,proposedPlan=proposed)
            raise DurableTaskExecutionError('PBL_PLAN_INVALID','项目计划经过修复仍未通过检查')
        save('plan_ready')
    # Revalidate persisted step snapshots against current trusted runtime before reuse.
    saved_completed=list(completed)
    checks=[]
    initial_files=starter_files(plan,STARTER_FILES)
    template_version=MULTI_TEMPLATE if plan.get('runtime') else PROJECT_TEMPLATE
    previous=initial_files
    for index in range(len(plan['steps'])):
        step=plan['steps'][index]
        existing=saved_completed[index]['candidate'] if index<len(saved_completed) else None
        if existing is None and isinstance(pending,dict) and pending.get('stepId')==step['id']:
            existing=pending.get('candidate')
        failure=failure_context if failure_context and failure_context.get('stepId')==step['id'] else {}
        issues=failure.get('issues') or []
        prior_candidate=failure.get('priorCandidate')
        previous_check_report=failure.get('previousCheckReport') or checkpoint.get('previousCheckReport')
        if not isinstance(previous_check_report,dict) or previous_check_report.get('stepId')!=step['id']:
            previous_check_report=None
        raw=existing
        for attempt in range(repairs.get(step['id'],0),3):
            context.progress(25+int(60*index/len(plan['steps'])),'pbl_build_step',f"正在制作并检查：{step['title']}")
            raw=existing
            try:
                if raw is None:
                    data={'topic':command['topic'],'plan':plan,'step':step,
                        'requiredChecks':[check for check in plan['checks'] if check['id'] in step['newCheckIds']],
                        'previousFiles':previous,'previousChecks':checks,'issues':issues,'priorCandidate':prior_candidate,
                        'previousCheckReport':previous_check_report}
                    implementation=None
                    if isinstance(pending,dict) and pending.get('stepId')==step['id'] and pending.get('implementation'):
                        try:
                            implementation=StepImplementation.model_validate(pending['implementation'])
                            validate_step_unit(plan,implementation.unit.model_dump())
                            if implementation.unit.stepId!=step['id'] or hash_files(implementation.referenceFiles)!=pending.get('implementationHash'):
                                implementation=None
                        except (ValueError,TypeError): implementation=None
                    if implementation is None:
                        raw=await model('repair_step' if issues else 'build_step',data)
                        implementation=StepImplementation.model_validate(raw)
                        if implementation.unit.stepId!=step['id']: raise ValueError('单步材料不属于当前步骤')
                        validate_step_unit(plan,implementation.unit.model_dump())
                        pending={'stepId':step['id'],'implementation':implementation.model_dump(mode='json'),
                                 'implementationHash':hash_files(implementation.referenceFiles)}
                        save('step_implemented')
                    # Run the immutable previous contract before spending a model call on new checks.
                    # A resumed implementation is re-executed; persisted reports never bypass this gate.
                    raw=implementation.model_dump(mode='json')
                    if checks:
                        context.progress(25+int(60*index/len(plan['steps'])),'pbl_previous_checks',f"正在确认前序功能：{step['title']}")
                        regression=await execute(implementation.referenceFiles,checks)
                        previous_check_report={'stepId':step['id'],'referenceHash':hash_files(implementation.referenceFiles),
                            'previousHash':hash_files(previous),'checkIds':[c['id'] for c in checks],**regression}
                        pending['previousCheckReport']=previous_check_report
                        if not regression['passed']:
                            failed=[r for r in regression['results'] if r['status']!='passed']
                            raise ValueError('本步代码未通过前序验收，尚未设计本步验收；对照 previousFiles、priorCandidate.referenceFiles 和 previousCheckReport 修复本步代码，保留前序检查及本步目标：'+json.dumps(failed,ensure_ascii=False)[:5000])
                    else:
                        previous_check_report={'stepId':step['id'],'referenceHash':hash_files(implementation.referenceFiles),
                            'previousHash':hash_files(previous),'checkIds':[],'skipped':True,'reason':'首步没有前序验收'}
                        pending['previousCheckReport']=previous_check_report
                    save('previous_checks_complete')
                    context.progress(25+int(60*index/len(plan['steps'])),'pbl_build_checks',f"正在根据代码设计验收：{step['title']}")
                    acceptance=await model('repair_checks' if issues else 'build_checks',{
                        **data,**implementation.model_dump(mode='json'),'referenceHash':hash_files(implementation.referenceFiles),
                        'previousCheckReport':previous_check_report})
                    # The checks call cannot replace the code it was asked to inspect.
                    raw={**acceptance,'referenceFiles':implementation.referenceFiles}
                    StepAcceptance.model_validate(acceptance)
                candidate=StepCandidate.model_validate(raw)
                if candidate.unit.stepId!=step['id']: raise ValueError('单步材料不属于当前步骤')
                validate_step_unit(plan,candidate.unit.model_dump())
                new=[c.model_dump(exclude_none=True) for c in candidate.checks]
                if len(new)!=len(step['newCheckIds']) or {c['id'] for c in new}!=set(step['newCheckIds']):
                    raise ValueError('本步检查编号与计划不一致')
                candidate.checks.sort(key=lambda check:step['newCheckIds'].index(check.id))
                planned={check['id']:check for check in plan['checks']}
                for check in candidate.checks:
                    if check.viewport is None: check.viewport=planned[check.id].get('viewport')
                if candidate.faultyFiles:
                    if not set(candidate.faultyFiles)<=set(plan['editableFiles']): raise ValueError('负例文件超出工程清单')
                    candidate.faultyFiles={**candidate.referenceFiles,**candidate.faultyFiles}
                new=[c.model_dump(exclude_none=True) for c in candidate.checks]
                validate_planned_checks(plan,new)
                if index>=len(saved_completed) or existing is None:
                    pending={'stepId':step['id'],'candidate':candidate.model_dump(mode='json')}
                save('step_candidate')
                cumulative=[*checks,*new]
                reference=await execute(candidate.referenceFiles,cumulative)
                prior=await execute(previous,new)
                faulty=None
                if candidate.faultyFiles and candidate.faultyCheckId in step['newCheckIds']:
                    faulty=await execute(candidate.faultyFiles,[c for c in new if c['id']==candidate.faultyCheckId])
                if not reference.get('passed'):
                    failed=[r for r in reference.get('results',[]) if r['status']!='passed']
                    raise ValueError('参考实现未通过累计检查（先核对需求、本步检查和代码；本步验收可修复，前序检查保留）: '+json.dumps(failed,ensure_ascii=False)[:5500])
                quality_warnings=[]
                if prior.get('passed'): quality_warnings.append('前一步工程已通过本步检查，教学增量可能不足')
                if faulty is None: quality_warnings.append('未提供可执行负例，负例区分度未验证')
                elif faulty.get('passed'): quality_warnings.append('模型负例也通过检查，负例区分度不足')
                item={'candidate':candidate.model_dump(mode='json'),'validated':True,
                    'qualityWarnings':quality_warnings,
                    'referenceHash':hash_files(candidate.referenceFiles),'faultyHash':hash_files(candidate.faultyFiles),
                    'evidence':{'reference':reference,'previous':prior,'faulty':faulty,'previousRegression':previous_check_report}}
                completed=completed[:index]+[item]+completed[index+1:]
                checks=cumulative; previous=candidate.referenceFiles
                if isinstance(pending,dict) and pending.get('stepId')==step['id']: pending=None
                if failure_context and failure_context.get('stepId')==step['id']: failure_context=None
                save('step_validated')
                break
            except (ValueError,TypeError) as exc:
                if isinstance(exc,InvalidProjectOutput):
                    raw=exc.raw
                    if isinstance(raw,dict) and isinstance(pending,dict) and pending.get('implementation'):
                        raw={**raw,'referenceFiles':pending['implementation']['referenceFiles']}
                prior_candidate=raw
                issues=[str(exc)[:6000]]; existing=None; pending=None
                repairs[step['id']]=attempt+1
                repair_totals[step['id']]=repair_totals.get(step['id'],0)+1
                completed=completed[:index]
                failure_context={'stepId':step['id'],'issues':issues,'priorCandidate':raw,'previousCheckReport':previous_check_report}
                save('step_repair',repair_count=attempt+1,issues=issues,lastCandidate=raw)
        else:
            save('failed',issues=issues,lastCandidate=raw)
            raise DurableTaskExecutionError('PBL_VALIDATION_FAILED','项目步骤经过修复仍未通过运行检查，请重试')
    final=await execute(previous,checks)
    if not final.get('passed'):
        save('failed')
        raise DurableTaskExecutionError('PBL_VALIDATION_FAILED','项目最终累计检查未通过')
    derived=validate_runtime_plan(plan)['cumulativeCheckIds']
    report={'passed':True,'templateVersion':template_version,'results':final['results'],'durationMs':final['durationMs'],
        'validatedSteps':len(completed),'skillVersions':versions,
        'qualityWarnings':[{'stepId':item['candidate']['unit']['stepId'],'message':warning} for item in completed for warning in item.get('qualityWarnings',[])]}
    artifact=ProjectArtifact(runtimeKind='sandpack_project' if plan.get('runtime') else 'react_app',runtime=runtime_for(plan),templateVersion=template_version,exerciseId=identifier,artifactVersion=1,topic=command['topic'],title=plan['title'],summary=plan['goal'],plan=plan,
        starterFiles=initial_files,tasks=[{**item['candidate']['unit'],'id':item['candidate']['unit']['stepId'],
            'cumulativeCheckIds':derived[item['candidate']['unit']['stepId']]} for item in completed],checks=checks,
        validationSummary={'passed':True,'templateVersion':template_version,'validatedSteps':len(completed),'qualityWarnings':report['qualityWarnings']})
    check_context(context)
    context.progress(95,'pbl_publish','项目累计检查通过，正在保存')
    check_context(context)
    repository.publish(owner,identifier,context.task_id,artifact,{'plan':plan,'completed':completed,'skillVersions':versions},report)
    if repository.get_owned(owner,identifier).artifact_public!=artifact.model_dump(mode='json'):
        raise DurableTaskExecutionError('PBL_SAVE_FAILED','项目保存检查失败')
    return result_ref(identifier)
