"""Durable, resumable generation with private checkpoints and fenced publication."""
import asyncio
from app.services.durable_task_handlers import DurableTaskExecutionError
from app.services.job_store import get_job
from .repository import PblRepository, StaleGeneration


def result_ref(exercise_id):
    return {'saved':True,'result_ref':{'resource_type':'pbl_exercise','exercise_id':exercise_id},
        'completion_message':'编程项目已就绪，可以开始实现'}


def check_context(context):
    if context.is_cancel_requested(): raise DurableTaskExecutionError('GENERATION_CANCELLED','练习生成已取消')
    if context.is_lease_valid is not None and not context.is_lease_valid():
        raise DurableTaskExecutionError('PBL_STALE_ATTEMPT','生成任务租约已过期')


async def guarded_operation(awaitable, context):
    """Cancel the HTTP coroutine promptly; subprocess validation has its own hard timeout."""
    check_context(context)
    task=asyncio.ensure_future(awaitable)
    try:
        while not task.done():
            await asyncio.wait({task},timeout=.2)
            check_context(context)
        result=await task
        check_context(context)
        return result
    finally:
        if not task.done():
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass


async def generate_exercise(command, context, *, repository=None):
    repository=repository or PblRepository(lease_context=context)
    owner,identifier=context.owner_user_id,command['exercise_id']
    check_context(context)
    row=repository.get_owned(owner,identifier)
    if row.artifact_public:
        if row.current_job_id!=context.task_id:
            raise DurableTaskExecutionError('PBL_ALREADY_PUBLISHED','练习已发布，无需重新生成')
        return result_ref(identifier)
    job=get_job(context.task_id)
    retry_of=job.retry_of_job_id if job else None
    if not repository.claim_generation(owner,identifier,context.task_id,retry_of):
        raise DurableTaskExecutionError('PBL_STALE_ATTEMPT','练习生成任务已被替代')
    # All unpublished requests use the same capability-bounded planning pipeline.
    # Old completed artifacts returned above keep their original runtime and checks.
    from .project_service import generate_project
    return await generate_project(command,context,repository)

class PblTaskHandler:
    def __call__(self, command, context):
        try: return asyncio.run(generate_exercise(command,context))
        except DurableTaskExecutionError: raise
        except StaleGeneration:
            raise DurableTaskExecutionError('PBL_STALE_ATTEMPT','生成已取消、过期或被替代') from None
        except Exception:
            # No candidate source or provider secrets in public errors or chained logs.
            raise DurableTaskExecutionError('PBL_GENERATION_FAILED','练习生成未完成，请稍后重试') from None
