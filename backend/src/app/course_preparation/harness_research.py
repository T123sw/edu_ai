"""Execute research and planning tools inside one native Harness session."""
import hashlib
import threading
import time
from pydantic import ValidationError

from .evidence_spans import evidence_context
from .research_agent import REGISTRY, ResearchError, RecoverableSourceError


class LearningPathTools:
    def __init__(self, agent, request, state, *, reserve, guard, timeout):
        self.agent, self.request, self.state = agent, request, state
        agent.upload_read_limit = max(8, 2*len(request.uploads))
        self.reserve, self.guard = reserve, guard
        if state.summary is not None and not state.draft_findings:
            self.state = state.model_copy(update={'draft_findings':state.summary.findings})
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
        schema, description = REGISTRY['report_research_blocker']
        self.tools['report_research_blocker'] = {'name':'report_research_blocker',
            'description':description, 'parameters':schema.model_json_schema()}

    @staticmethod
    def source_key(name, arguments):
        if name not in ('search_sources', 'fetch_source'):
            return None
        import json
        if name == 'fetch_source':
            arguments = {'candidate_id':arguments.get('candidate_id')}
        return name + ':' + hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()

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
        if (self.state.summary is not None and self.state.summary.coverage
                and all(row.status == 'covered' for row in self.state.summary.coverage)):
            names.append('save_course_plan')
        return [*names, 'report_research_blocker']

    def call(self, name, arguments):
        with self.lock:
            try:
                self.check()
                if self.result is not None:
                    return {'ok': False, 'error': 'WORKFLOW_FINISHED', 'message': '结果已保存，请结束本轮。'}
                if self.state.calls >= self.agent.max_calls:
                    raise ResearchError('BUDGET_EXHAUSTED', '研究动作次数已达上限')
                self.persist(self.state.model_copy(update={'calls': self.state.calls + 1}))
                before = self.state
                try:
                    if name not in self.available() or name not in self.tools:
                        raise ValueError('当前工具不可用；先完成研究汇总才能提交路径，并遵守来源与预算限制')
                    args = REGISTRY[name][0].model_validate(arguments)
                    key = self.source_key(name, arguments)
                    from .research_coverage import validate_coverage, validate_ready
                    if name == 'report_research_blocker':
                        validate_coverage(args.coverage, self.state.brief, self.state.draft_findings)
                        if all(r.status == 'covered' for r in args.coverage):
                            raise ValueError('报告资料不足时至少有一条未覆盖或部分覆盖的需求')
                        updated = self.state.model_copy(update={'blocker':args, 'path':None, 'summary':None, 'review':None})
                    else:
                        if name == 'finalize_research_summary':
                            selected = [f for f in self.state.draft_findings if f.finding_id in args.finding_ids]
                            validate_coverage(args.coverage, self.state.brief, selected)
                        if name == 'save_course_plan':
                            validate_ready(self.state.summary, self.state.brief)
                        if key and self.state.source_failures.get(key, 0) >= 2:
                            raise ValueError('该请求已暂时失败两次，请换来源/查询，或 report_research_blocker')
                        updated = self.agent._execute(name, args, self.request, self.state,
                            timeout=max(.1, min(25, self.deadline-time.monotonic())), reserve=self.persist)
                    if name == 'finalize_research_summary' and any(row.status != 'covered' for row in args.coverage):
                        updated = updated.model_copy(update={'phase':'research'})
                    # New evidence/findings invalidate an earlier summary. Planning
                    # can return to research without switching Harness sessions.
                    if name in ('fetch_source', 'record_evidence_finding', 'record_research_finding'):
                        updated = updated.model_copy(update={'phase': 'research', 'summary': None, 'path': None})
                    updated = updated.model_copy(update={'errors': 0, 'last_error': None,
                        'source_failures':{k:v for k,v in updated.source_failures.items() if k != key},
                        'trace': (*updated.trace, {'call': updated.calls, 'phase': before.phase,
                                                  'tool': name, 'status': 'ok'})})
                    self.check()
                    self.persist(updated)
                except RecoverableSourceError as exc:
                    key = self.source_key(name, arguments)
                    failures = {**self.state.source_failures, key:self.state.source_failures.get(key, 0)+1}
                    error = {'code':exc.code, 'message':str(exc), 'recoverable':True,
                             'attempts':failures[key], 'retry_allowed':failures[key]<2}
                    self.check()
                    self.persist(self.state.model_copy(update={'source_failures':failures, 'last_error':error,
                        'trace':(*self.state.trace, {'call':self.state.calls, 'phase':self.state.phase,
                                                   'tool':name, 'status':'error', **error})}))
                    return {'ok':False, 'error':error, 'available_tools':self.available(),
                            'remaining_budget':self.agent.read_budget(self.state)}
                except (ValueError, ValidationError) as exc:
                    failed = self.agent._error(self.state, 'INVALID_TOOL_RESULT', str(exc)[:1600])
                    self.persist(failed)
                    return {'ok': False, 'error': failed.last_error, 'available_tools': self.available()}
                data = {}
                if name == 'search_sources':
                    previous_ids = {c.candidate_id for c in before.candidates}
                    data['candidates'] = [c.model_dump(mode='json') for c in updated.candidates if c.candidate_id not in previous_ids]
                    data['message'] = '仅返回新增候选；已有候选继续有效，不重复返回。'
                elif name == 'fetch_source':
                    data['evidence'] = evidence_context(updated)[len(before.evidence):]
                elif name in ('record_evidence_finding', 'record_research_finding'):
                    finding = next(f for f in updated.draft_findings if f.finding_id == args.finding_id)
                    data['finding'] = {'finding_id':finding.finding_id, 'claim':finding.claim,
                        'citations':[{'source_id':c.source_id} for c in finding.citations]}
                    data['message'] = '引用已逐字校验并保存；原文见此前 evidence，不重复返回。'
                elif name in ('finalize_research_summary', 'save_research_summary'):
                    data['summary'] = updated.summary.model_dump(mode='json', exclude={'findings'})
                    data['summary']['finding_ids'] = [f.finding_id for f in updated.summary.findings]
                elif name == 'report_research_blocker':
                    self.result = updated
                    data['research_blocker'] = updated.blocker.model_dump(mode='json')
                    data['research_stopped'] = True
                elif name == 'save_course_plan':
                    self.result = updated
                    data['path_saved'] = True
                return {'ok': True, **data, 'phase': updated.phase, 'available_tools': self.available(),
                        'remaining_actions': self.agent.max_calls-updated.calls,
                        'remaining_budget':self.agent.read_budget(updated)}
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
                                 'searches': max(0, 6-state.searches), **agent.read_budget(state)}}
