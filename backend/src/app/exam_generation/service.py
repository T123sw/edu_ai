"""Connect immutable inputs and private checkpoints to the durable worker."""
import asyncio
import hashlib
import os
import time
from uuid import NAMESPACE_URL, uuid5
from app.integrations.deeptutor.client import DeepTutorClient, DeepTutorConfig, DeepTutorError
from app.services.durable_task_handlers import DurableTaskExecutionError
from .repository import GenerationRepository, GenerationConflict
from .sources import GenerationSources
from .snapshots import SnapshotCodec
from .validation import complete_result
from .progress import question_progress, question_status


def configured_client():
    return DeepTutorClient(DeepTutorConfig(base_url=os.getenv('EDU_DEEPTUTOR_URL', 'http://127.0.0.1:8026'),
        token=os.getenv('EDU_DEEPTUTOR_TOKEN', '')))


class ExamGenerationHandler:
    def __init__(self, repository=None, sources=None, codec=None, client_factory=None):
        self.repository = repository or GenerationRepository()
        self.sources = sources or GenerationSources()
        self.codec = codec or SnapshotCodec()
        self.client_factory = client_factory or configured_client

    def __call__(self, command, context):
        try:
            return asyncio.run(self.run(command, context))
        except DeepTutorError as exc:
            if exc.status_code in {502, 503, 504}:
                from app.services.durable_task_executor import RetryableTaskError
                raise RetryableTaskError('出题服务连接中断，将继续原任务', code='EXAM_TRANSPORT_INTERRUPTED') from None
            raise DurableTaskExecutionError('EXAM_UPSTREAM_REJECTED', '出题服务未接受请求') from None
        except DurableTaskExecutionError:
            raise
        except Exception:
            # Parser/provider exceptions can contain source text or credentials.
            raise DurableTaskExecutionError('EXAM_GENERATION_FAILED', '试卷生成未完成，请检查模型配置及资料后重试') from None

    async def run(self, command, context):
        owner, gid = context.owner_user_id, command['generation_id']
        attempt = context.attempt_count or 1
        repo = self.repository
        row = repo.get(owner, gid, include_events=False)
        checkpoint_id = row.get('checkpoint_id') or row['request']['request_id']
        if context.task_id != gid:
            # General task-center retries create a fresh private generation,
            # retaining the original immutable inputs and encrypted snapshot.
            request = {**row['request'], 'request_id': str(uuid5(NAMESPACE_URL, context.task_id))}
            row = repo.create(owner, request, sources=row['sources'], encrypted_snapshot=row['encrypted_snapshot'])
            gid = row['id']
        row = repo.claim(owner, gid, attempt)
        saved_progress = row.get('question_progress')
        if saved_progress:
            context.progress(*question_status(saved_progress))
        repo.update(owner, gid, attempt, {'job_id': context.task_id, 'checkpoint_id': checkpoint_id})
        def check():
            if context.is_lease_valid is not None and not context.is_lease_valid():
                raise DurableTaskExecutionError('EXAM_STALE_ATTEMPT', '生成任务已由新工作器接管')
        check()
        providers = self.codec.read(owner, row['encrypted_snapshot'])
        if row['parsed_sources'] is None:
            context.progress(5, 'parsing', '正在读取上传资料')
            def remote_task(task):
                check()
                current = repo.get(owner, gid, include_events=False)
                repo.update(owner, gid, attempt, {'remote_parse_tasks': [*current['remote_parse_tasks'], task]})
            parsed = await asyncio.to_thread(self.sources.parse, owner, row['sources'], providers['pdf_parser'],
                canceled=lambda: context.is_cancel_requested() or (context.is_lease_valid is not None and not context.is_lease_valid()),
                on_remote_task=remote_task)
            check()
            repo.update(owner, gid, attempt, {'parsed_sources': parsed})
            row = repo.get(owner, gid, include_events=False)
        if context.is_cancel_requested():
            return {'saved': False, 'completion_message': '任务已取消'}
        async with self.client_factory() as client:
            if row['turn_id'] is None:
                llm = providers.get('vision_llm') if any(s.get('images') for s in row['parsed_sources']) else None
                llm = llm or providers['llm']
                request = {k: v for k, v in row['request'].items() if k != 'sources'}
                request.update(checkpoint_id=checkpoint_id, parsed_sources=row['parsed_sources'], runtime_model={
                    'model': llm['model'], 'base_url': llm['base_url'], 'api_key': llm.get('api_key', ''),
                    'api_format': 'openai_chat', 'binding': llm.get('binding', 'openai'),
                    'reasoning_effort': llm.get('reasoning_effort'), 'supports_vision': llm.get('supports_vision', False)})
                text_llm = providers['llm']
                request['runtime_text_model'] = {
                    'model': text_llm['model'], 'base_url': text_llm['base_url'],
                    'api_key': text_llm.get('api_key', ''), 'api_format': 'openai_chat',
                    'binding': text_llm.get('binding', 'openai'),
                    'reasoning_effort': text_llm.get('reasoning_effort'),
                    'supports_vision': text_llm.get('supports_vision', False)}
                check()
                remote = await client.start(owner=owner, request=request)
                check()
                repo.update(owner, gid, attempt, {k: remote[k] for k in ('session_id', 'turn_id')})
                row = repo.get(owner, gid, include_events=False)
            # Status also reaps a turn whose service process was lost. Failure is
            # explicit; a process restart must never masquerade as completion.
            await client.status(owner=owner, turn_id=row['turn_id'])
            stream = client.internal_events(owner=owner, turn_id=row['turn_id'], after_seq=row['last_seq'])
            pending = None
            last_stage = None
            batch = []
            last_flush = time.monotonic()
            last_control_check = 0.0
            def flush():
                nonlocal last_flush
                if batch:
                    check()
                    repo.events_batch(owner, gid, attempt, batch)
                    batch.clear()
                    last_flush = time.monotonic()
            try:
                while True:
                    # Poll control state at bounded intervals, not for every token.
                    # Every durable write still checks the current lease/attempt.
                    if time.monotonic() - last_control_check >= 0.25:
                        last_control_check = time.monotonic()
                        if context.is_cancel_requested():
                            await client.cancel(owner=owner, turn_id=row['turn_id'])
                            return {'saved': False, 'completion_message': '任务已取消'}
                        check()
                    if pending is None:
                        pending = asyncio.create_task(anext(stream))
                    done, _ = await asyncio.wait({pending}, timeout=0.3)
                    if not done:
                        flush()
                        continue
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        break
                    pending = None
                    batch.append(event)
                    if len(batch) >= 500 or time.monotonic() - last_flush >= 0.5:
                        flush()
                    progress_value = question_progress(event)
                    if progress_value is not None and (saved_progress is None or
                            (progress_value['total'] == saved_progress['total'] and
                             progress_value['processed'] > saved_progress['processed'])):
                        saved_progress = progress_value
                        # Persist the slot and event cursor before publishing its progress.
                        flush()
                        context.progress(*question_status(progress_value))
                    stage = event.get('stage')
                    labels = {'exploring': (20, '正在整理资料'), 'planning': (35, '正在提取题型与结构'), 'quizzing': (40, '正在生成第 1 题')}
                    if not saved_progress and stage in labels and stage != last_stage:
                        progress, message = labels[stage]
                        context.progress(progress, stage, message)
                        last_stage = stage
            finally:
                if pending is not None and not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                await stream.aclose()
                flush()
            status = await client.status(owner=owner, turn_id=row['turn_id'])
            row = repo.get(owner, gid, include_events=False)
            if status['status'] != 'completed' or not complete_result(row):
                raise DurableTaskExecutionError('EXAM_UPSTREAM_INCOMPLETE', '出题服务未完整生成试卷，原任务记录已保留')
            check()
            context.progress(100, 'completed', '试卷已生成')
            return {'saved': True, 'result_ref': {'resource_type': 'exam_generation', 'generation_id': gid},
                    'completion_message': '试卷已生成'}
