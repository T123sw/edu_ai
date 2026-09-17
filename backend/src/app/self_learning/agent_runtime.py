"""Bounded read-only teaching loop with durable checkpoints and fenced publication."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import re
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
        spec = tools.registry.get(call['function']['name'])
        if spec and spec.effect == 'write':
            timeout = min(spec.timeout_seconds, deadline - time.monotonic())
            if timeout <= 0:
                raise AgentFailure('DEADLINE_EXCEEDED')
            try:
                return await asyncio.wait_for(tools.dispatch_write(call), timeout=timeout)
            except TimeoutError:
                return {'ok': False, 'error': {'code': 'TIMEOUT', 'message': '操作超时，可按原请求检查或重试', 'retryable': True}}
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
            if 'preparation_receipts' in snapshot:
                packet['preparation_receipts'] = snapshot['preparation_receipts']
            return result
        except TimeoutError:
            return {'ok': False, 'error': {'code': 'TIMEOUT', 'message': '资料读取超时', 'retryable': True}}
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    async def execute(self, claim):
        builder = ContextBuilder(self.learning)
        builder.authorize(claim['owner'], claim['course_id'], claim['topic_id'], claim['request']['reading_context'])
        enrichment = bool(getattr(self.learning, 'memory', None))
        schemas_size = len(json.dumps(LearningTools(self.learning, claim, {}).schemas(), ensure_ascii=False).encode())
        preparation_enabled = bool(getattr(self.learning, 'preparations', None))
        reserve = 2200 if preparation_enabled else 256
        context_budget = max(1000, 16000 - schemas_size - reserve) if enrichment else 24000
        state = copy.deepcopy(claim['checkpoint']) or {'packet': builder.build(claim, budget=context_budget), 'rounds': 0, 'tools': 0, 'pending': [], 'repair_used': False}
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
            memory = getattr(self.learning, 'memory', None)
            if memory:
                current_epoch = memory.epoch(claim['owner'])
                if current_epoch != packet.get('memory_epoch'):
                    if state['pending'] and tools.reconcile_memory_epoch(state['pending'][0], current_epoch):
                        # The previous worker committed this very preference write
                        # before losing its checkpoint. Replay its receipt first.
                        packet['memory_epoch'] = current_epoch
                    else:
                        raise AgentFailure('MEMORY_CONTEXT_CHANGED')
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
                    if call['function']['name'] == 'update_learning_preference' and result.get('ok') and result['data'].get('changed'):
                        fresh = builder.build(claim, budget=context_budget)
                        if fresh['memory_epoch'] != result['data']['memory_epoch']:
                            raise AgentFailure('MEMORY_CONTEXT_CHANGED')
                        # Rebuild after an explicit change; don't continue to
                        # inject old preference text or suppressed source messages.
                        index = max(i for i, m in enumerate(packet['messages']) if m.get('tool_calls'))
                        tail = copy.deepcopy(packet['messages'][index:])
                        tail[0]['content'] = None
                        fresh['messages'].extend(tail)
                        fresh['handles'].update(packet['handles'])
                        fresh['citations'].update(packet['citations'])
                        fresh['actions'] = packet.get('actions', {})
                        fresh['preparation_receipts'] = packet.get('preparation_receipts', {})
                        packet.clear()
                        packet.update(fresh)
                    self.repository.save(claim, state, 'reading_resources', {**intent, 'status': 'completed', 'result': result})
                packet['messages'].append({'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result, ensure_ascii=False)})
                state['pending'].pop(0)
                self.repository.save(claim, state)
            state['rounds'] += 1
            self.repository.save(claim, state)
            mounted = tools.schemas() if state['tools'] < 6 and (not state['repair_used'] or state.get('repair_allows_tools')) else []
            if enrichment:
                byte_size = lambda schema: len(json.dumps({'messages': packet['messages'], 'tools': schema}, ensure_ascii=False).encode())
                if byte_size(mounted) > 16000:
                    mounted = []  # reserve the remaining context for the final answer
                if not mounted and not state.get('closing_prompt'):
                    packet['messages'].append({'role':'user','content':'本轮工具阶段已结束。根据已有资料和真实收据给出最终 JSON 对象：answer_markdown、citation_ids、suggested_action_ids、observation；不再调用工具，不输出空白。'})
                    state['closing_prompt'] = True
                if byte_size(mounted) > 16000:
                    raise AgentFailure('CONTEXT_BUDGET_EXCEEDED')
            try:
                reply = await model.complete(packet['messages'], mounted, deadline=deadline)
            except AgentFailure as exc:
                if exc.code != 'MODEL_EMPTY_RESPONSE' or state.get('empty_response_repaired'):
                    raise
                state['empty_response_repaired'] = True
                packet['messages'].append({'role':'user','content':'上一条模型响应为空。请输出一个非空的合法 JSON 最终答复；沿用已读取资料和已成功操作的收据，不重复写操作。'})
                continue
            if reply['calls']:
                if not mounted or state['tools'] >= 6 or (state['repair_used'] and not state.get('repair_allows_tools')):
                    raise AgentFailure('TOOL_BUDGET_EXHAUSTED')
                packet['messages'].append({'role': 'assistant', 'content': reply['content'] or None, 'tool_calls': reply['calls']})
                state['pending'] = copy.deepcopy(reply['calls'])
                self.repository.save(claim, state)
                continue
            try:
                answer = AnswerResult.model_validate(answer_json(reply['content']))
                if set(answer.citation_ids) - set(packet['citations']) or set(answer.suggested_action_ids) - set(packet.get('actions', {})):
                    raise ValueError('unknown reference')
                if preparation_enabled:
                    self.validate_preparation_claim(claim, packet, answer.answer_markdown)
                if answer.observation:
                    if not memory or set(answer.observation.source_message_ids) != {claim['turn_id'] + ':user'}:
                        raise ValueError('unknown observation source')
                    from .contracts import Actor
                    course_view = self.learning.progress_service.reader.read(Actor(user_id=claim['owner']), claim['course_id'])
                    objectives = {o.objective_id for t in course_view.topics if t.topic_id == claim['topic_id'] for o in t.objectives}
                    if not set(answer.observation.objective_ids) <= objectives:
                        raise ValueError('unknown observation objective')
            except ValueError:
                if state['repair_used']:
                    raise AgentFailure('ANSWER_SCHEMA_INVALID')
                state['repair_used'] = True
                state['repair_allows_tools'] = preparation_enabled
                packet['messages'].append({'role': 'assistant', 'content': reply['content'][:3000]})
                instruction = ('回答结构、引用或操作收据无效。本轮未获得提交收据就不能说已提交/已保存，历史回答不是本轮收据。'
                    '如当前请求明确要求生成保存或修改资料，必须先实际调用已挂载的准备工具；目标含糊则询问。'
                    '最终必须输出规定 JSON 对象，accepted 只能说任务已接收，不能说资料已完成。') if preparation_enabled else '回答结构或引用无效。只用已有引用 ID 修正为指定 JSON，不调用工具。'
                packet['messages'].append({'role': 'user', 'content': instruction})
                continue
            builder.authorize(claim['owner'], claim['course_id'], claim['topic_id'], claim['request']['reading_context'])
            citations = [packet['citations'][cid] for cid in answer.citation_ids]
            for citation in packet['citations'].values():
                material = exact_material(self.learning, claim['owner'], ResourceRef.model_validate(citation['resource_ref']))
                if hashlib.sha256(material_text(material).encode()).hexdigest() != citation['content_hash']:
                    raise AgentFailure('SOURCE_CHANGED')
            return {**answer.model_dump(), 'citations': citations, 'role_version': packet['role_version'],
                    'actions': [packet['actions'][key] for key in answer.suggested_action_ids],
                    **({'preparation_receipts': list(packet.get('preparation_receipts', {}).values())} if preparation_enabled else {}),
                    **({'memory_epoch': packet['memory_epoch']} if memory else {}),
                    'source_revision': packet['source_revision'], 'model_rounds': state['rounds'], 'tool_attempts': state['tools']}
        raise AgentFailure('MODEL_BUDGET_EXHAUSTED')

    @staticmethod
    def validate_preparation_claim(claim, packet, answer):
        # Persisted service receipts, never model text or historical assistant
        # messages, are evidence of effects. Keep claims conservative on repair.
        question = claim['request']['question']
        operation_request = bool(re.search(r'生成|保存|修改|修订|create|save|revise', question, re.I) and re.search(r'资料|文档|练习|课件|报告|当前这份|resource|document|quiz', question, re.I))
        status_query = bool(re.search(r'进度|状态|好了吗|完成了吗|生成了吗|怎么样', question))
        if status_query and not re.search(r'请生成|帮我生成|生成并保存|请修改|帮我修改', question):
            operation_request = False
        asserted = re.search(r'(?:已|已经)(?:提交|保存|创建|生成|修改|完成)|任务.{0,8}(?:已受理|已接收)|(?:have |has )?(?:submitted|saved|created)', answer, re.I)
        if not asserted or not (operation_request or status_query):
            return
        receipts = [r for r in packet.get('preparation_receipts', {}).values()
            if not operation_request or (r.get('origin_ref') or {}).get('message_id') == claim['turn_id'] + ':user']
        if not receipts:
            raise ValueError('preparation claim has no current-turn receipt')
        delivered = re.search(r'(?:资料|文档|练习|任务).{0,8}(?:已完成|已保存|准备好)|(?:已|已经)(?:生成|保存|修改).{0,8}(?:资料|文档|练习)', answer)
        if delivered and not any(r['status'] == 'succeeded' for r in receipts):
            raise ValueError('accepted preparation is not delivered')

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
            scoped = self.learning.for_scope(claim['owner'], claim['course_id'])
            runtime = self if scoped is self.learning else LearningAgentRuntime(scoped, self.repository, self.model_factory)
            result = asyncio.run(runtime.guarded(claim))
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
        if getattr(self.learning, 'preparations', None):
            self.learning.preparations.service.start()
        if getattr(self.learning, 'summaries', None):
            self.learning.summaries.start()
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
        if getattr(self.learning, 'preparations', None):
            self.learning.preparations.service.stop()
        if getattr(self.learning, 'summaries', None):
            self.learning.summaries.stop(grace_seconds=1)
        if self.thread:
            self.thread.join(timeout=grace_seconds)
