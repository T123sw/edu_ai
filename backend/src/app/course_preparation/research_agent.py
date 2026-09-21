"""Bounded, checkpointable intent → research → path → review tool loop."""
import hashlib
from datetime import datetime, timezone

from pydantic import ValidationError

from .citation_locator import locate_quote

from .research_contracts import (
    Candidate, FetchArgs, LearningPath, PathReview, ResearchBrief, ResearchRequest,
    ResearchState, ResearchSummary, SearchArgs, SourceEvidence, Finding, FinalizeSummary, ReferencedFinding, ResearchBlocker, ReadEvidenceArgs,
)


class ResearchError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f'{code}: {message}')


class RecoverableSourceError(ResearchError):
    pass


REGISTRY = {
    'read_research_evidence': (ReadEvidenceArgs, '从已读证据回读精确原文或 citation_ref，不请求网络，不消耗外部读取预算；省略的上下文不能替代原文。'),
    'report_research_blocker': (ResearchBlocker, '无法取得足够依据时结束研究，保存每条需求覆盖情况、具体缺口和补充建议；不生成或交付路径。'),
    'record_evidence_finding': (ReferencedFinding, '保存有依据的研究结论，citation_refs 只能选择 evidence.passages 中真实的引用编号；无需重写原文。'),
    'record_research_finding': (Finding, '记录一条有已读原文依据的结论，短引用必须逐字匹配正文；同 finding_id 可修正。'),
    'finalize_research_summary': (FinalizeSummary, '依据已保存结论汇总，并在 coverage 逐条判定证据能否完整支持原始需求；部分支持必须 partial，不通过缩小目标声称 covered。'),
    'save_preparation_brief': (ResearchBrief, '理解用户本次学习目标、时间与排除项；用户要求引用原话；附件要求使用 source_ref 由程序回填原文；材料缺失写入 material_gaps，不作为 exclusions。'),
    'search_sources': (SearchArgs, '搜索与当前学习目标相关的可靠资料；只返回候选摘要，不代表正文已读取。'),
    'fetch_source': (FetchArgs, '读取候选正文的5000字符节选；offset_chars默认0，需要后文时传5000、10000等偏移。取得可引用的source_id。'),
    'save_research_summary': (ResearchSummary, '汇总已读正文，逐条 finding 附 source_id 和原文短引文；不能引用搜索摘要。'),
    'save_course_plan': (LearningPath, '提交完整课程对象 title、summary、nodes（全部节点数组）、limitations，修订也必须完整重交，不能提交单个节点或拆成多次调用。覆盖要求、先修、活动、自测和时间；不是已生成教学资源。'),
    'submit_path_review': (PathReview, '独立检查用户原话、研究结论与学习路径，发现事实、覆盖、时间或先修问题必须 fail。'),
}
MOUNTS = {'intent': ('save_preparation_brief',),
          'research': ('search_sources', 'fetch_source', 'read_research_evidence', 'save_research_summary'),
          'plan': ('read_research_evidence', 'save_course_plan',), 'review': ('submit_path_review',)}


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f'{label}不能重复')


class ResearchAgent:
    def __init__(self, *, model, sources, max_calls=30, source_policy="open", extra_context=None, incremental_findings=False):
        self.upload_read_limit = 8
        self.incremental_findings = incremental_findings
        self.extra_context = extra_context or {}
        self.source_policy = source_policy
        self.model, self.sources, self.max_calls = model, sources, max_calls

    def read_budget(self, state):
        # Legacy checkpoints predate the split counter. Completed upload excerpts
        # establish a lower bound without refunding any spent reads.
        uploads = max(state.upload_reads, sum(e.url.startswith('upload://') for e in state.evidence))
        return {'upload_reads': max(0, self.upload_read_limit-uploads),
                'web_reads': max(0, 8-max(0, state.reads-uploads))}

    def can_read(self, url, state):
        key = 'upload_reads' if url.startswith('upload://') else 'web_reads'
        return self.read_budget(state)[key] > 0

    def tools(self, phase, state=None):
        names = MOUNTS.get(phase, ())
        if self.incremental_findings and phase == 'research':
            names = tuple(n for n in names if n != 'save_research_summary') + ('record_evidence_finding', 'finalize_research_summary')
        if self.source_policy == "uploaded_only":
            names = tuple(n for n in names if n != "search_sources")
        if state is not None and not state.evidence:
            names = tuple(n for n in names if n != 'read_research_evidence')
        if state is not None and phase == 'research':
            names = tuple(name for name in names
                          if not (name == 'search_sources' and (state.searches >= 6 or self.read_budget(state)['web_reads'] == 0))
                          and not (name == 'fetch_source' and not any(self.read_budget(state).values())))
        if state is not None and phase == 'research' and state.candidates:
            available = False
            for candidate in state.candidates:
                if not self.can_read(candidate.url, state): continue
                pieces = sorted((e for e in state.evidence if e.candidate_id == candidate.candidate_id), key=lambda e:e.offset_chars)
                if not pieces or pieces[-1].total_chars is None:
                    available = True; break
                cursor = 0
                for piece in pieces:
                    if piece.offset_chars > cursor: break
                    cursor = max(cursor, piece.offset_chars + len(piece.content))
                if cursor < pieces[-1].total_chars:
                    available = True; break
            if not available: names = tuple(n for n in names if n != 'fetch_source')
        return [{'type': 'function', 'function': {
            'name': name, 'description': REGISTRY[name][1],
            'parameters': REGISTRY[name][0].model_json_schema(),
        }} for name in names]

    def step(self, request: ResearchRequest, state: ResearchState, *, timeout=90,
             reserve=None) -> ResearchState:
        if state.phase == 'done':
            return state
        if state.calls >= self.max_calls:
            raise ResearchError('BUDGET_EXHAUSTED', '研究决策次数已达上限')
        state = state.model_copy(update={'calls': state.calls + 1})
        def persist(value):
            nonlocal state
            state = value
            if reserve:
                reserve(value)
        persist(state)  # Persist spent call BEFORE contacting an external model.
        context = {**self.extra_context, 'request': request.model_dump(mode='json'), **state.model_dump(mode='json'),
                   'remaining_budget': {'model_calls': self.max_calls - state.calls,
                                        'searches': max(0, 6 - state.searches),
                                        **self.read_budget(state)}}
        if state.phase == 'intent':
            from .intake_references import with_references
            context['input_documents'] = with_references(context.get('input_documents', []))
        if self.incremental_findings:
            from .research_context_view import build_research_context_view
            context.update(build_research_context_view(state, required_ids=(), max_bytes=48000))
        # Review is a fresh independent request: no generator self-assessment or tool history.
        if state.phase == 'review':
            context.pop('trace', None)
            context.pop('review', None)
        name, raw_args = None, None
        try:
            mounted = self.tools(state.phase, state)
            name, raw_args = self.model.decide(context, mounted, timeout=timeout)
            if name not in {tool['function']['name'] for tool in mounted}:
                return self._error(state, 'TOOL_NOT_AVAILABLE', '当前阶段未挂载该工具')
            args = REGISTRY[name][0].model_validate(raw_args)
            updated = self._execute(name, args, request, state, timeout=min(timeout, 25), reserve=persist)
            reused = updated is state
            entry = {'call': state.calls, 'phase': state.phase, 'tool': name, 'status': 'reused' if reused else 'ok'}
            return updated.model_copy(update={'errors': state.errors if reused else 0,
                                             'last_error': updated.last_error if reused or name=='read_research_evidence' else None,
                                             'trace': (*updated.trace, entry)})
        except (ValueError, ValidationError) as exc:
            message = str(exc)[:1600]
            if isinstance(exc, ValidationError):
                message = '; '.join(f'{e["loc"]}: {e["msg"]}' for e in exc.errors(include_input=False))[:1600]
            failed = self._error(state, 'INVALID_TOOL_RESULT', message)
            if name is not None:
                failed = failed.model_copy(update={'last_error': {**failed.last_error,
                    'attempted_tool': name, 'arguments': raw_args}})
            elif getattr(self.model, 'last_rejected_decision', None):
                failed = failed.model_copy(update={'last_error': {**failed.last_error,
                    'rejected_model_response': self.model.last_rejected_decision}})
            return failed

    def _error(self, state, code, message):
        if state.errors >= 2:
            raise ResearchError('AGENT_NO_PROGRESS', message)
        return state.model_copy(update={'errors': state.errors + 1,
            'last_error': {'code': code, 'message': message},
            'trace': (*state.trace, {'call': state.calls, 'phase': state.phase, 'status': 'error', 'code': code, 'message': message})})

    def _execute(self, name, args, request, state, *, timeout, reserve):
        if name == 'read_research_evidence':
            result=self.read_evidence(state,args)
            return state.model_copy(update={'last_error':{'code':'EVIDENCE_READ_RECEIPT','evidence':result}})
        if name == 'save_preparation_brief':
            unique([r.requirement_id for r in args.requirements], '要求ID')
            from .intake import validate_brief
            from .intake_references import resolve_requirements
            args = resolve_requirements(args, getattr(self, 'extra_context', {}).get('input_documents', []))
            validate_brief(args, request, getattr(self, 'extra_context', {}).get('input_documents', []))
            from .schemas import SourcePolicy
            mode = 'uploaded_only' if request.source_policy.mode == 'uploaded_only' else (args.source_policy.mode if args.source_policy else request.source_policy.mode)
            args = args.model_copy(update={'source_policy': SourcePolicy(mode=mode)})
            if request.overrides.total_minutes and args.total_minutes != request.overrides.total_minutes:
                raise ValueError('必须遵守本次明确设置的学习时间')
            if request.overrides.language and args.language != request.overrides.language:
                raise ValueError('必须遵守本次明确设置的语言')
            return state.model_copy(update={'brief': args, 'phase': 'research'})
        if name == 'search_sources':
            if self.source_policy == "uploaded_only":
                raise PermissionError("UPLOADED_ONLY_NETWORK_FORBIDDEN")
            if state.searches >= 6:
                raise ResearchError('BUDGET_EXHAUSTED', '搜索次数已达上限')
            if any(t.get('query') == args.query for t in state.trace):
                raise ValueError('同查询已执行，请使用候选资料或修改查询解决具体缺口')
            state = state.model_copy(update={'searches': state.searches + 1})
            if reserve:
                reserve(state)
            hits = self.sources.search(args.query, limit=5, timeout=timeout)
            candidates = {c.url: c for c in state.candidates}
            for hit in hits:
                url = hit['url']
                candidates.setdefault(url, Candidate(candidate_id='src_' + hashlib.sha256(url.encode()).hexdigest()[:20],
                    url=url, title=hit['title'][:300], snippet=hit['snippet'][:600]))
            return state.model_copy(update={'candidates': tuple(candidates.values())[:30 + len(request.uploads)],
                'trace': (*state.trace, {'query': args.query, 'hits': len(hits)})})
        if name == 'fetch_source':
            candidate = next((c for c in state.candidates if c.candidate_id == args.candidate_id), None)
            if not candidate:
                raise ValueError('只能读取本任务搜索发现的候选')
            if any(e.candidate_id == args.candidate_id and e.offset_chars == args.offset_chars for e in state.evidence):
                raise ValueError('该正文已读取，请使用已有证据；不要重复抓取')
            if not self.can_read(candidate.url, state):
                raise ValueError('该类来源的读取预算已耗尽；选择其他允许来源或报告资料缺口')
            upload_reads = max(state.upload_reads, sum(e.url.startswith('upload://') for e in state.evidence))
            state = state.model_copy(update={'reads': state.reads + 1,
                'upload_reads': upload_reads + int(candidate.url.startswith('upload://'))})
            if reserve:
                reserve(state)
            snapshot = self.sources.read_snapshot(candidate.url, timeout=timeout) if hasattr(self.sources, 'read_snapshot') else None
            full_content = snapshot.content if snapshot else self.sources.read(candidate.url, timeout=timeout)
            if len(full_content.strip()) < (20 if candidate.url.startswith('upload://') else 100):
                raise ValueError('正文未能有效提取，不能使用搜索摘要代替')
            previous=[e for e in state.evidence if e.candidate_id==candidate.candidate_id]
            if any((snapshot and e.snapshot_id and e.snapshot_id!=snapshot.snapshot_id)
                   or full_content[e.offset_chars:e.offset_chars+len(e.content)]!=e.content for e in previous):
                raise ResearchError('SOURCE_VERSION_CONFLICT','来源正文版本已变化；保留旧证据，不能混合分页版本')
            if args.offset_chars >= len(full_content):
                raise ValueError(f'正文已结束，总长 {len(full_content)} 字符；不能继续读取该偏移，请使用已有证据')
            content = full_content[args.offset_chars:args.offset_chars + 5000]
            digest = hashlib.sha256(content.encode()).hexdigest()
            evidence = SourceEvidence(source_id='ev_' + hashlib.sha256((candidate.url + str(args.offset_chars) + (snapshot.snapshot_id if snapshot else '') + digest).encode()).hexdigest()[:24],
                candidate_id=candidate.candidate_id, url=candidate.url, title=candidate.title,
                content=content, offset_chars=args.offset_chars, total_chars=len(full_content),
                snapshot_id=snapshot.snapshot_id if snapshot else None,
                snapshot_sha256=snapshot.content_sha256 if snapshot else None,
                canonical_url=snapshot.canonical_url if snapshot else None,
                next_offset=args.offset_chars+5000 if args.offset_chars+5000<len(full_content) else None, content_sha256=digest, retrieved_at=snapshot.retrieved_at if snapshot else datetime.now(timezone.utc).isoformat())
            return state.model_copy(update={'evidence': (*state.evidence, evidence)})
        if name == 'record_evidence_finding':
            from .evidence_spans import span_registry
            spans = span_registry(state)
            unique(args.citation_refs, '引用编号')
            if not set(args.citation_refs) <= spans.keys(): raise ValueError('引用编号不属于已读正文')
            finding = Finding(finding_id=args.finding_id,claim=args.claim,citations=tuple(spans[key] for key in args.citation_refs))
            return self._execute('record_research_finding',finding,request,state,timeout=timeout,reserve=reserve)
        if name == 'record_research_finding':
            checked = self._execute('save_research_summary', ResearchSummary(overview=args.claim, findings=(args,)),
                request, state, timeout=timeout, reserve=reserve)
            findings = {finding.finding_id:finding for finding in state.draft_findings}
            normalized = checked.summary.findings[0]
            if findings.get(args.finding_id) == normalized:
                # A resumed native session may replay a validated finding.
                # Keep the stored finding/summary; the action still costs budget.
                return state
            if args.finding_id not in findings and len(findings) >= 12: raise ValueError('研究结论已达上限')
            findings[args.finding_id] = normalized
            return state.model_copy(update={'draft_findings':tuple(findings.values()),'trace':checked.trace})
        if name == 'finalize_research_summary':
            findings = {finding.finding_id:finding for finding in state.draft_findings}
            unique(args.finding_ids, '结论ID')
            if not set(args.finding_ids) <= findings.keys(): raise ValueError('只能汇总已保存的结论 ID')
            return self._execute('save_research_summary', ResearchSummary(overview=args.overview,
                findings=tuple(findings[key] for key in args.finding_ids),limitations=args.limitations,coverage=args.coverage),
                request,state,timeout=timeout,reserve=reserve)
        if name == 'save_research_summary':
            evidence = {e.source_id: e for e in state.evidence}
            if not evidence or (not state.searches and not any(e.url.startswith('upload://') for e in state.evidence)):
                raise ValueError('必须搜索并读取至少一个实际来源正文后再汇总')
            read_urls = {e.url for e in state.evidence}
            if any(f'upload://{ref.document_id}/{ref.version}' not in read_urls for ref in request.uploads if ref.usage in ('primary', 'coverage')):
                raise ValueError('用户指定的核心上传资料必须先读取正文')
            unique([f.finding_id for f in args.findings], '研究结论ID')
            citation_errors, normalized_findings, corrections = [], [], []
            for finding in args.findings:
                citations = []
                for citation in finding.citations:
                    source = evidence.get(citation.source_id)
                    if source is not None and citation.quote not in source.content:
                        # Exact text, same already-read page, uniquely located excerpt only.
                        matches = [(e, locate_quote(e.content, citation.quote))
                                   for e in state.evidence if e.url == source.url and e.snapshot_id == source.snapshot_id]
                        matches = [(e, quote) for e, quote in matches if quote is not None]
                        if len(matches) == 1:
                            resolved, raw_quote = matches[0]
                            corrections.append({'event': 'citation_span_resolved',
                                'finding_id': finding.finding_id, 'from_source_id': citation.source_id,
                                'to_source_id': resolved.source_id,
                                'format_adjusted': raw_quote != citation.quote})
                            citation = citation.model_copy(update={'source_id': resolved.source_id, 'quote': raw_quote})
                            source = resolved
                    if source is None or citation.quote not in source.content:
                        matches = [e.source_id for e in state.evidence if citation.quote in e.content]
                        from difflib import SequenceMatcher
                        hint = ''
                        if source is not None:
                            match = SequenceMatcher(None, citation.quote, source.content, autojunk=False).find_longest_match()
                            if match.size >= 12:
                                hint = '; 可核对的原文片段=' + repr(source.content[match.b:match.b + min(match.size, 100)])
                        citation_errors.append(f'{finding.finding_id}: {citation.source_id}, quote={citation.quote!r}; 原文实际所在ID={matches}' + hint)
                    citations.append(citation)
                normalized_findings.append(finding.model_copy(update={'citations': tuple(citations)}))
            if citation_errors:
                raise ValueError('以下引用与已读原文不匹配，请全部修正；逐字复制简短原文，不翻译、不改写、不引用未读取的后文：' + '; '.join(citation_errors))
            args = args.model_copy(update={'findings': tuple(normalized_findings)})
            if args.unresolved_gaps:
                raise ValueError('unresolved_gaps 仅填写尚未解决的核心缺口；已解决或无缺口时必须传空数组 []，不能填“无”。当前提交：' + str(args.unresolved_gaps))
            return state.model_copy(update={'summary': args, 'phase': 'plan',
                                            'trace': (*state.trace, *corrections)})
        if name == 'save_course_plan':
            self._validate_path(args, state)
            return state.model_copy(update={'path': args, 'phase': 'review'})
        if name == 'submit_path_review':
            requirements = {r.requirement_id for r in state.brief.requirements}
            if set(args.checked_requirement_ids) != requirements:
                raise ValueError('独立审阅必须逐项覆盖所有要求')
            if args.decision == 'pass':
                return state.model_copy(update={'review': args, 'phase': 'done'})
            if state.repairs >= 2:
                raise ResearchError('QUALITY_GATE_FAILED', '学习路径两次修正后仍未通过审阅')
            return state.model_copy(update={'review': args, 'repairs': state.repairs + 1,
                'phase': args.repair_phase, 'path': None,
                'summary': None if args.repair_phase in ('intent', 'research') else state.summary})
        raise ValueError('unsupported tool')

    def read_evidence(self, state, args):
        from .research_context_view import read_research_evidence
        result=read_research_evidence(state,**args.model_dump())
        evidence=next(e for e in state.evidence if e.source_id==result['source_id'])
        if hasattr(self.sources,'authorize_read'):
            self.sources.authorize_read(evidence.url)
        return result

    @staticmethod
    def _validate_path(path, state):
        if state.summary.coverage:
            from .research_coverage import validate_ready
            validate_ready(state.summary, state.brief)
        requirements = {r.requirement_id for r in state.brief.requirements}
        findings = {f.finding_id: f for f in state.summary.findings}
        sources = {e.source_id for e in state.evidence}
        unique([n.node_key for n in path.nodes], '知识点ID')
        seen, covered, errors = set(), set(), []
        if state.brief.node_count is not None and len(path.nodes) != state.brief.node_count:
            errors.append(f'节点数 {len(path.nodes)} 不符合用户明确要求的 {state.brief.node_count} 个节点')
        for node in path.nodes:
            if not set(node.prerequisite_keys) <= seen:
                errors.append(f'{node.node_key}: 先修必须在路径前面存在；可选 {sorted(seen)}')
            if not set(node.requirement_ids) <= requirements:
                errors.append(f'{node.node_key}: 不存在的需求 {sorted(set(node.requirement_ids) - requirements)}')
            if not set(node.finding_ids) <= findings.keys() or not set(node.source_ids) <= sources:
                errors.append(f'{node.node_key}: 包含不存在的研究结论或已读来源ID')
            cited = {c.source_id for fid in node.finding_ids if fid in findings for c in findings[fid].citations}
            if not set(node.source_ids) <= cited:
                errors.append(f'{node.node_key}: source_ids 与 finding_ids 不匹配；当前结论支持的 source_ids 只有 {sorted(cited)}')
            for row in state.summary.coverage:
                if (row.requirement_id in node.requirement_ids and row.kind == 'knowledge'
                        and not set(row.finding_ids).intersection(node.finding_ids)):
                    errors.append(f'{node.node_key}: 需求 {row.requirement_id} 未使用 coverage 中的支撑结论')
            covered.update(node.requirement_ids)
            seen.add(node.node_key)
        if covered != requirements:
            errors.append(f'学习路径缺少需求 {sorted(requirements - covered)}')
        minutes = sum(n.minutes for n in path.nodes)
        if minutes > state.brief.total_minutes:
            errors.append(f'总时间 {minutes} 分钟超过用户约束 {state.brief.total_minutes} 分钟')
        if errors:
            raise ValueError('; '.join(errors))
