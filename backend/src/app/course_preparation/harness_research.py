"""Execute research and planning tools inside one native Harness session."""
import threading
import time
from pydantic import ValidationError

from .evidence_spans import evidence_context
from .research_agent import REGISTRY, ResearchError


class LearningPathTools:
    def __init__(self, agent, request, state, *, reserve, guard, timeout):
        self.agent, self.request, self.state = agent, request, state
        self.reserve, self.guard = reserve, guard
        self.deadline = time.monotonic() + timeout
        self.lock = threading.RLock()
        self.result = None
        self.invalid = False
        self.fatal = None
        self.continuous = True
        # Capability catalogue is fixed for the session; availability is checked
        # again against live state on every call, including batched calls.
        self.tools = {t['function']['name']: t['function']
                      for phase in ('research', 'plan') for t in agent.tools(phase)}

    def schemas(self):
        return [{'name': name, 'description': spec['description'], 'inputSchema': spec['parameters']}
                for name, spec in self.tools.items()]

    def check(self):
        if self.fatal:
            raise self.fatal
        if time.monotonic() >= self.deadline:
            raise ResearchError('BUDGET_EXHAUSTED', '资料研究与路径会话超时')
        self.guard()

    def persist(self, state):
        self.reserve(state)
        self.state = state

    def available(self):
        if self.result is not None:
            return []
        names = [t['function']['name'] for t in self.agent.tools('research', self.state)]
        if self.state.summary is not None:
            names.append('save_course_plan')
        return names

    def call(self, name, arguments):
        with self.lock:
            try:
                self.check()
                if self.result is not None:
                    return {'ok': False, 'error': 'PATH_ALREADY_SUBMITTED', 'message': '路径已保存，请结束本轮。'}
                if self.state.calls >= self.agent.max_calls:
                    raise ResearchError('BUDGET_EXHAUSTED', '研究动作次数已达上限')
                self.persist(self.state.model_copy(update={'calls': self.state.calls + 1}))
                before = self.state
                try:
                    if name not in self.available() or name not in self.tools:
                        raise ValueError('当前工具不可用；先完成研究汇总才能提交路径，并遵守来源与预算限制')
                    args = REGISTRY[name][0].model_validate(arguments)
                    updated = self.agent._execute(name, args, self.request, self.state,
                        timeout=max(.1, min(25, self.deadline-time.monotonic())), reserve=self.persist)
                    # New evidence/findings invalidate an earlier summary. Planning
                    # can return to research without switching Harness sessions.
                    if name in ('fetch_source', 'record_evidence_finding', 'record_research_finding'):
                        updated = updated.model_copy(update={'phase': 'research', 'summary': None, 'path': None})
                    updated = updated.model_copy(update={'errors': 0, 'last_error': None,
                        'trace': (*updated.trace, {'call': updated.calls, 'phase': before.phase,
                                                  'tool': name, 'status': 'ok'})})
                    self.check()
                    self.persist(updated)
                except (ValueError, ValidationError) as exc:
                    failed = self.agent._error(self.state, 'INVALID_TOOL_RESULT', str(exc)[:1600])
                    self.persist(failed)
                    return {'ok': False, 'error': failed.last_error, 'available_tools': self.available()}
                data = {}
                if name == 'search_sources':
                    data['candidates'] = [c.model_dump(mode='json') for c in updated.candidates]
                elif name == 'fetch_source':
                    data['evidence'] = evidence_context(updated)[len(before.evidence):]
                elif name in ('record_evidence_finding', 'record_research_finding'):
                    data['finding'] = next(f.model_dump(mode='json') for f in updated.draft_findings if f.finding_id == args.finding_id)
                elif name in ('finalize_research_summary', 'save_research_summary'):
                    data['summary'] = updated.summary.model_dump(mode='json')
                elif name == 'save_course_plan':
                    self.result = updated
                    data['path_saved'] = True
                return {'ok': True, **data, 'phase': updated.phase, 'available_tools': self.available(),
                        'remaining_actions': self.agent.max_calls-updated.calls}
            except Exception as exc:
                # MCP cannot carry Python exceptions. Preserve the original error
                # for the adapter and prevent any subsequent side effects.
                self.fatal = exc
                return {'ok': False, 'error': getattr(exc, 'code', type(exc).__name__),
                        'message': '执行已停止；不能继续工具操作。'}


def workflow_context(agent, request, state):
    return {**agent.extra_context, **state.model_dump(mode='json'), 'phase': 'learning_path',
            'request': request.model_dump(mode='json'), 'evidence': evidence_context(state),
            'remaining_budget': {'actions': agent.max_calls-state.calls,
                                 'searches': max(0, 6-state.searches), 'reads': max(0, 8-state.reads)}}
