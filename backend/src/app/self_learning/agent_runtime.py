"""Bounded read-only teaching loop with durable checkpoints and fenced publication."""
import asyncio
import copy
import json
import time
from threading import Event, Thread
from fastapi import HTTPException
from .context_builder import ContextBuilder
from .contracts import ResourceRef
from .model_adapter import LearningModelAdapter, strict_json
from .resource_reader import exact_material, material_text
from .tools import LearningTools
from .turn_contracts import AnswerResult, AgentFailure
from .turn_repository import LostLease
import hashlib


class LearningAgentRuntime:
    def __init__(self, learning, repository, model_factory=None):
        self.learning, self.repository = learning, repository
        self.model_factory = model_factory or (lambda owner: LearningModelAdapter(learning.model_factory(owner)))
        self.stopping = Event()
        self.thread = None

    async def execute(self, claim):
        builder = ContextBuilder(self.learning)
        builder.authorize(claim['owner'], claim['course_id'], claim['topic_id'], claim['request']['reading_context'])
        state = copy.deepcopy(claim['checkpoint'])
        if not state.get('packet'):
            recovered = state.get('recovered_preparations', {})
            state = {'packet': builder.build(claim), 'rounds': 0, 'tools': 0, 'pending': [], 'repair_used': False}
            if recovered:
                state['packet']['preparation_receipts'] = recovered
                state['packet']['messages'].insert(-1, {'role':'user','content':'本轮已提交的真实后台任务回执：'+json.dumps(recovered,ensure_ascii=False)})
        packet = state['packet']
        tools = LearningTools(self.learning, claim, packet)
        model = self.model_factory(claim['owner'])
        deadline = time.monotonic() + max(0, claim['deadline'] - self.repository.clock())
        while state['rounds'] < 8:
            memory = getattr(self.learning, 'memory_adapter', None)
            if memory:
                from app.chat.memory.lifecycle import MemoryChanged
                try:
                    if not packet.get('memory_context'): raise MemoryChanged('MEMORY_CONTEXT_NOT_CAPTURED')
                    memory.validate(claim['owner'], packet['memory_context'])
                except MemoryChanged:
                    packet = builder.build(claim)
                    state.update(packet=packet, pending=[], repair_used=False)
                    tools = LearningTools(self.learning, claim, packet)
                    self.repository.save(claim, state)
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
                    result = tools.dispatch(call)
                    self.repository.save(claim, state, 'reading_resources', {**intent, 'status': 'completed', 'result': result})
                packet['messages'].append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result, ensure_ascii=False)})
                state['pending'].pop(0)
                self.repository.save(claim, state)
            state['rounds'] += 1
            self.repository.save(claim, state)
            reply = await model.complete(packet['messages'], tools.schemas() if state['tools'] < 6 and not state['repair_used'] else [], deadline=deadline)
            if memory:
                try: memory.validate(claim['owner'], packet['memory_context'])
                except MemoryChanged: continue
            if reply['calls']:
                if state['tools'] >= 6 or state['repair_used']:
                    raise AgentFailure('TOOL_BUDGET_EXHAUSTED')
                writes=[call for call in reply['calls'] if tools.registry.get(call['function']['name']) and tools.registry[call['function']['name']].effect=='write']
                if writes and len(reply['calls'])!=1: raise AgentFailure('TOOL_WRITE_BATCH_FORBIDDEN')
                packet['messages'].append({'role': 'assistant', 'content': reply['content'] or None, 'tool_calls': reply['calls']})
                # Execution consumes this queue; preserve the assistant's immutable
                # tool-call transcript for the next provider request.
                state['pending'] = copy.deepcopy(reply['calls'])
                self.repository.save(claim, state)
                continue
            try:
                answer = AnswerResult.model_validate(strict_json(reply['content']))
                if 'prepare_learning_material' in tools.registry and not packet.get('preparation_receipts'):
                    if state.get('handoff_repair_used'):
                        raise AgentFailure('PREPARATION_NOT_SUBMITTED')
                    state.update(handoff_repair_used=True, repair_used=False)
                    packet['messages'].append({'role':'assistant','content':reply['content']})
                    packet['messages'].append({'role':'user','content':'本轮用户明确要求保存或修订资料，但本轮没有真实准备任务回执。历史回答不代表当前任务已执行。必须先调用 prepare_learning_material 并取得真实回执，不能声称已提交或已完成。'})
                    self.repository.save(claim,state)
                    continue
                if answer.observation:
                    room=self.learning.room(claim['course_id'],claim['owner'])
                    chapter=next(c for c in room['chapters'] if c['id']==claim['topic_id'])
                    objectives={o['objective_id'] for o in chapter.get('objectives',[])}
                    if answer.observation.source_quote not in claim['request']['question'] or not set(answer.observation.objective_ids)<=objectives:
                        raise ValueError('observation source not current user or objective')
                if set(answer.citation_ids) - set(packet['citations']) or set(answer.suggested_action_ids)-set(packet.get('preparation_receipts',{})):
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
            for citation in citations:
                material = exact_material(self.learning, claim['owner'], ResourceRef.model_validate(citation['resource_ref']))
                if hashlib.sha256(material_text(material).encode()).hexdigest() != citation['content_hash']:
                    raise AgentFailure('SOURCE_CHANGED')
            observation={**answer.observation.model_dump(),'source_refs':[claim['turn_id']+':user'],'evaluator':'model','status':'hypothesis'} if answer.observation else None
            return {**answer.model_dump(), 'observation':observation,'citations': citations, 'role_version': packet['role_version'],
                    'source_revision': packet['source_revision'], 'model_rounds': state['rounds'], 'tool_attempts': state['tools'], 'memory_context': packet.get('memory_context'), 'preparation_receipts': list(packet.get('preparation_receipts',{}).values())}
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
            summaries=getattr(self.learning,'summaries',None)
            if summaries:
                try: asyncio.run(summaries.refresh(claim['owner'],claim['session_id']))
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('Learning summary refresh failed: %s',claim['session_id'])
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
