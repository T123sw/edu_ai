"""Checkpoint preparation stages; research and planning can share a continuous Harness session."""
from datetime import datetime, timezone
import hashlib
from .research_contracts import ResearchState, Candidate
from .runner import StepResult
from .adapters.sources import upload_url
from .adapters.documents import DocumentUnreadable
from .research_agent import ResearchError


class ResearchStages:
    def __init__(self,repository,agent_factory,documents,*,memory=None,node_reviewer=None):
        self.node_reviewer=node_reviewer
        self.repository,self.agent_factory,self.documents,self.memory=repository,agent_factory,documents,memory

    def _request(self,context):
        return self.repository.get(owner_user_id=context.owner_user_id,preparation_id=context.preparation_id).request

    def _decision(self,context,checkpoint):
        request=self._request(context)
        if request.target and 'target_snapshot' not in checkpoint:
            checkpoint={**checkpoint, 'target_snapshot':self.repository.authorizer.targets.read(context.owner_user_id,request.target)}
        if self.memory:
            checkpoint=self.memory.prepare(context,checkpoint,request)
        state=ResearchState.model_validate(checkpoint.get('research_state',{}))
        if checkpoint.get('research_attempt') != context.attempt_no:
            state=state.model_copy(update={'errors':0,'blocker':None,'source_failures':{}})
            checkpoint={**checkpoint,'research_attempt':context.attempt_no}
            checkpoint.pop('research_blocker',None)
        # Upgrade old bounded excerpts: a short final slice proves EOF without rereading.
        totals={e.candidate_id:e.offset_chars+len(e.content) for e in state.evidence if e.total_chars is None and len(e.content)<5000}
        if totals:
            state=state.model_copy(update={'evidence':tuple(e.model_copy(update={'total_chars':totals[e.candidate_id],
                'next_offset':e.offset_chars+5000 if e.offset_chars+5000<totals[e.candidate_id] else None})
                if e.candidate_id in totals else e for e in state.evidence)})
        from .intake import effective_request
        request = effective_request(request, checkpoint)
        agent=self.agent_factory(context,request,checkpoint)
        agent.extra_context = {**agent.extra_context, 'input_documents': checkpoint.get('input_documents', [])}
        def reserve(value):
            self.repository.checkpoint(context,{**checkpoint,'research_state':value.model_dump(mode='json')})
        remaining=(datetime.fromisoformat(context.deadline)-datetime.now(timezone.utc)).total_seconds()
        if state.blocker is not None:
            checkpoint['research_blocker']=state.blocker.model_dump(mode='json')
            checkpoint.pop('plan',None)
            checkpoint.pop('research_summary',None)
            self.repository.checkpoint(context,checkpoint)
            raise ResearchError('RESEARCH_INSUFFICIENT',state.blocker.reason)
        if state.phase in ('research', 'plan') and hasattr(agent.model, 'run_learning_path'):
            def guard():
                self.repository.heartbeat(context)
                if self.memory:
                    self.memory.validate(context, checkpoint)
            state=agent.model.run_learning_path(agent,request,state,reserve=reserve,guard=guard,
                                               timeout=max(1,min(480,remaining)))
        else:
            state=agent.step(request,state,timeout=max(1,min(90,remaining)),reserve=reserve)
        if self.memory:
            self.memory.validate(context,checkpoint)
        checkpoint={**checkpoint,'research_state':state.model_dump(mode='json')}
        for key,value in (('brief',state.brief),('research_summary',state.summary),('plan',state.path)):
            if value is not None: checkpoint[key]=value.model_dump(mode='json')
        if state.blocker is not None:
            checkpoint['research_blocker']=state.blocker.model_dump(mode='json')
            checkpoint.pop('plan',None)
            checkpoint.pop('research_summary',None)
            self.repository.checkpoint(context,checkpoint)
            raise ResearchError('RESEARCH_INSUFFICIENT',state.blocker.reason)
        return checkpoint,state

    def normalize(self,context):
        from .route_adjustment import eligible
        request=self._request(context)
        if eligible(request):
            checkpoint=dict(context.checkpoint)
            checkpoint['target_snapshot']=self.repository.authorizer.targets.read(context.owner_user_id,request.target)
            checkpoint=self.memory.prepare(context,checkpoint,request)
            checkpoint['route_only_adjustment']=True
            base=checkpoint['target_snapshot']['manifest']
            checkpoint['brief']={'goal':request.goal,'audience':base['audience'],'language':request.overrides.language or 'zh-CN',
                'total_minutes':request.overrides.total_minutes or base['estimated_minutes'],'assumptions':base.get('assumptions',[])}
            return StepResult(checkpoint,'research_scope',reason='NO_UPLOADS')
        from .intake import understand_next_document
        checkpoint, pending = understand_next_document(self, context, dict(context.checkpoint), request)
        if pending:
            return StepResult(checkpoint)
        checkpoint,state=self._decision(context,checkpoint)
        if state.brief is None: return StepResult(checkpoint)
        uploads=self._request(context).uploads
        return StepResult(checkpoint,'ingest' if uploads else 'research_scope',
            reason=None if uploads else 'NO_UPLOADS')

    def ingest(self,context):
        checkpoint=dict(context.checkpoint)
        request=self._request(context)
        completed=list(checkpoint.get('ingested_documents',[]))
        if len(completed)<len(request.uploads):
            ref=request.uploads[len(completed)]
            parsed=self.documents.parse(context.owner_user_id,ref)
            if parsed['defects'] and ref.usage in ('auto','primary','coverage'):
                raise DocumentUnreadable('CORE_SOURCE_UNREADABLE',parsed['defects'])
            metadata=self.documents.authorize(context.owner_user_id,ref)
            completed.append({**ref.model_dump(),'source_hash':parsed['source_hash'],
                'parser':parsed['parser'],'defects':parsed['defects'],'characters':len(parsed['content'])})
            state=ResearchState.model_validate(checkpoint['research_state'])
            url=upload_url(ref)
            candidate=Candidate(candidate_id='src_'+hashlib.sha256(url.encode()).hexdigest()[:20],
                url=url,title=metadata['filename'],snippet='用户上传资料；必须读取正文，不能把本说明作为证据')
            state=state.model_copy(update={'candidates':(*state.candidates,candidate)})
            checkpoint.update(ingested_documents=completed,research_state=state.model_dump(mode='json'))
        return StepResult(checkpoint,'research_scope' if len(completed)==len(request.uploads) else None)

    def research_scope(self,context):
        if context.checkpoint.get('route_only_adjustment'):
            checkpoint=dict(context.checkpoint)
            checkpoint['research_summary']={'overview':'保留已交付资料及其来源；本次只修改路径安排，不引入新知识。','findings':[]}
            return StepResult(checkpoint,'plan')
        checkpoint,state=self._decision(context,dict(context.checkpoint))
        return StepResult(checkpoint,'plan' if state.phase in ('plan','review','done') else None)

    def plan(self,context):
        if context.checkpoint.get('route_only_adjustment'):
            from .route_adjustment import plan
            return plan(self,context)
        checkpoint,state=self._decision(context,dict(context.checkpoint))
        if state.phase in ('intent','research'): return StepResult(checkpoint,'research_scope',reason='PATH_REVIEW_RESEARCH_REPAIR')
        return StepResult(checkpoint,'research_nodes' if state.phase=='done' else None)

    def research_nodes(self,context):
        if context.checkpoint.get('route_only_adjustment'):
            self.memory.validate(context,context.checkpoint)
            return StepResult(dict(context.checkpoint),'produce')
        # The reviewed route defines the node-level source subset. Exact evidence
        # is rechecked here before generation receives any resource specification.
        checkpoint=dict(context.checkpoint)
        state=ResearchState.model_validate(checkpoint['research_state'])
        if state.phase!='done' or state.review is None or state.review.decision!='pass':
            raise ResearchError('PATH_NOT_REVIEWED','路径未通过独立审阅')
        if self.memory:
            self.memory.validate(context,checkpoint)
        checked=dict(checkpoint.get('node_research_checks',{}))
        pending=next((n for n in state.path.nodes if n.node_key not in checked),None)
        if self.node_reviewer and pending:
            if state.calls >= 60: raise ResearchError('BUDGET_EXHAUSTED','节点研究调用上限')
            state=state.model_copy(update={'calls':state.calls+1})
            checkpoint['research_state']=state.model_dump(mode='json')
            self.repository.checkpoint(context,checkpoint)
            decision=self.node_reviewer(context,checkpoint,state,pending)
            if self.memory: self.memory.validate(context,checkpoint)
            if not decision.sufficient:
                repairs=checkpoint.get('node_research_repairs',0)+1
                if repairs>2: raise ResearchError('NODE_EVIDENCE_GAP','节点证据两轮补充后仍不足')
                state=state.model_copy(update={'phase':'research','summary':None,'path':None,'review':None,
                    'last_error':{'code':'NODE_EVIDENCE_GAP','message':decision.reason,'gap_queries':list(decision.gap_queries)}})
                checkpoint.update(research_state=state.model_dump(mode='json'),node_research_repairs=repairs,node_research_checks={})
                checkpoint.pop('plan',None); checkpoint.pop('research_summary',None)
                return StepResult(checkpoint,'research_scope',reason='NODE_EVIDENCE_GAP')
            checked[pending.node_key]=decision.model_dump(mode='json')
            checkpoint['node_research_checks']=checked
            if len(checked)<len(state.path.nodes): return StepResult(checkpoint)
        sources={e.source_id:e for e in state.evidence}
        findings={f.finding_id:f for f in state.summary.findings}
        node_evidence={}
        for node in state.path.nodes:
            selected=[]
            for finding_id in node.finding_ids:
                finding=findings[finding_id]
                for citation in finding.citations:
                    source=sources[citation.source_id]
                    if citation.quote not in source.content: raise ResearchError('EVIDENCE_CHANGED','节点引用失效')
                    selected.append({'finding_id':finding_id,'claim':finding.claim,
                        'source_id':source.source_id,'url':source.url,'quote':citation.quote,'source_hash':source.content_sha256})
            if not selected: raise ResearchError('NODE_EVIDENCE_GAP','节点缺少已读依据')
            node_evidence[node.node_key]=selected
        checkpoint['node_evidence']=node_evidence
        return StepResult(checkpoint,'produce')

    def handlers(self):
        return {name:getattr(self,name) for name in ('normalize','ingest','research_scope','plan','research_nodes')}
