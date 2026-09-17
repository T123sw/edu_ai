"""Bounded read-only teaching loop with durable checkpoints and fenced publication."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import time
from threading import Event, Thread
from fastapi import HTTPException
from .context_builder import ContextBuilder
from .contracts import ResourceRef
from .model_adapter import LearningModelAdapter, answer_json
from .resource_reader import exact_material, material_text
from .tools import LearningTools
from .turn_contracts import AnswerResult, AgentFailure
from .turn_repository import LostLease
import hashlib


class LearningAgentRuntime:
    def __init__(self, learning, repository, model_factory=None):
        self.learning, self.repository = learning, repository
        self.model_factory = model_factory
        self.stopping = Event()
        self.thread = None

    async def call_tool(self, tools, packet, call, deadline):
        # P3 handlers are reads only. Isolate their mutable reference registry so a
        # timed-out local I/O operation cannot change a later model context.
        snapshot = copy.deepcopy(packet)
        isolated = LearningTools(self.learning, tools.turn, snapshot)
        spec = tools.registry.get(call['function']['name'])
        timeout = min(spec.timeout_seconds if spec else 3, deadline - time.monotonic())
        if timeout <= 0:
            raise AgentFailure('DEADLINE_EXCEEDED')
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='learning-read')
        try:
            future = asyncio.wrap_future(executor.submit(isolated.dispatch, call))
            result = await asyncio.wait_for(future, timeout=timeout)
            packet['handles'], packet['citations'] = snapshot['handles'], snapshot['citations']
            return result
        except TimeoutError:
            return {'ok': False, 'error': {'code': 'TIMEOUT', 'message': '资料读取超时', 'retryable': True}}
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    async def execute(self, claim):
        builder = ContextBuilder(self.learning)
        builder.authorize(claim['owner'], claim['course_id'], claim['topic_id'], claim['request']['reading_context'])
        state = copy.deepcopy(claim['checkpoint']) or {'packet': builder.build(claim), 'rounds': 0, 'tools': 0, 'pending': [], 'repair_used': False}
        packet = state['packet']
        tools = LearningTools(self.learning, claim, packet)
        if self.model_factory:
            model = self.model_factory(claim['owner'])
        else:
            from app.services.runtime_config_resolver import runtime_config_resolver
            snapshot = claim['request'].get('_config_snapshot', {})
            config = runtime_config_resolver.resolve('llm', owner_user_id=claim['owner'], snapshot=snapshot)
            if snapshot.get('llm') and config.get('_revision_id') != snapshot['llm'].split(':', 1)[1]:
                raise AgentFailure('CONFIG_REVISION_UNAVAILABLE')
            model = LearningModelAdapter.from_config(config)
        deadline = time.monotonic() + max(0, claim['deadline'] - self.repository.clock())
        while state['rounds'] < 8:
            builder.authorize(claim['owner'], claim['course_id'], claim['topic_id'], claim['request']['reading_context'])
            while state['pending']:
                call = state['pending'][0]
                if state['tools'] >= 6:
                    result = {'ok': False, 'error': {'code': 'BUDGET_EXHAUSTED', 'message': '工具额度已用完'}}
                else:
                    state['tools'] += 1
                    operation = f"{claim['attempt']}:{state['rounds']}:{state['tools']}"
                    intent = {'operation_id': operation, 'call': call, 'status': 'intent'}
                    self.repository.save(claim, state, 'reading_resources', intent)
                    result = await self.call_tool(tools, packet, call, deadline)
                    self.repository.save(claim, state, 'reading_resources', {**intent, 'status': 'completed', 'result': result})
                packet['messages'].append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result, ensure_ascii=False)})
                state['pending'].pop(0)
                self.repository.save(claim, state)
            state['rounds'] += 1
            self.repository.save(claim, state)
            reply = await model.complete(packet['messages'], tools.schemas() if state['tools'] < 6 and not state['repair_used'] else [], deadline=deadline)
            if reply['calls']:
                if state['tools'] >= 6 or state['repair_used']:
                    raise AgentFailure('TOOL_BUDGET_EXHAUSTED')
                packet['messages'].append({'role': 'assistant', 'content': reply['content'] or None, 'tool_calls': reply['calls']})
                state['pending'] = copy.deepcopy(reply['calls'])
                self.repository.save(claim, state)
                continue
            try:
                answer = AnswerResult.model_validate(answer_json(reply['content']))
                if set(answer.citation_ids) - set(packet['citations']) or answer.suggested_action_ids:
                    raise ValueError('unknown reference')
            except ValueError:
                if state['repair_used']:
                    raise AgentFailure('ANSWER_SCHEMA_INVALID')
                state['repair_used'] = True
                packet['messages'].append({'role': 'assistant', 'content': reply['content']})
                packet['messages'].append({'role': 'user', 'content': '回答结构或引用无效。只用已有引用 ID 修正为指定 JSON，不调用工具。'})
                continue
            builder.authorize(claim['owner'], claim['course_id'], claim['topic_id'], claim['request']['reading_context'])
            citations = [packet['citations'][cid] for cid in answer.citation_ids]
            for citation in packet['citations'].values():
                material = exact_material(self.learning, claim['owner'], ResourceRef.model_validate(citation['resource_ref']))
                if hashlib.sha256(material_text(material).encode()).hexdigest() != citation['content_hash']:
                    raise AgentFailure('SOURCE_CHANGED')
            return {**answer.model_dump(), 'citations': citations, 'role_version': packet['role_version'],
                    'source_revision': packet['source_revision'], 'model_rounds': state['rounds'], 'tool_attempts': state['tools']}
        raise AgentFailure('MODEL_BUDGET_EXHAUSTED')

    async def guarded(self, claim):
        async def watch():
            while True:
                if self.stopping.is_set():
                    raise LostLease()
                self.repository.heartbeat(claim)
                await asyncio.sleep(.5)
        execution, watcher = asyncio.create_task(self.execute(claim)), asyncio.create_task(watch())
        try:
            done, _ = await asyncio.wait([execution, watcher], return_when=asyncio.FIRST_COMPLETED)
            if watcher in done:
                await watcher
            return await execution
        finally:
            execution.cancel()
            watcher.cancel()
            await asyncio.gather(execution, watcher, return_exceptions=True)

    def run_once(self):
        claim = self.repository.claim()
        if claim is None:
            return False
        try:
            result = asyncio.run(self.guarded(claim))
            self.repository.finish(claim, result=result)
        except LostLease:
            pass
        except Exception as exc:
            code = exc.code if isinstance(exc, AgentFailure) else 'CONTEXT_UNAVAILABLE' if isinstance(exc, HTTPException) else 'ANSWER_FAILED'
            try:
                self.repository.finish(claim, error=code)
            except LostLease:
                pass
        return True

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stopping.clear()
        def poll():
            while not self.stopping.is_set():
                try:
                    worked = self.run_once()
                except Exception:
                    worked = False
                if not worked:
                    self.stopping.wait(.5)
        self.thread = Thread(target=poll, name='learning-answer-worker', daemon=True)
        self.thread.start()

    def stop(self, grace_seconds=10):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=grace_seconds)
