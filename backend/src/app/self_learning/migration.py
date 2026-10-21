"""Read-only scan, restartable import and evidence-based reconciliation.

Never invent missing history, resolve an unknown version to latest, or overwrite
newer facts. The original source stays available as an immutable audit archive.
"""
import copy
import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid5,NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import ConversationMessage
from .contracts import Actor,ResourceRef
from .db_models import LearningTopicSession,LearningEventRecord
from .migration_models import LearningMigrationLedger as Ledger,LearningRolloutScope as Scope
from .progress_repository import digest
from .progress_contracts import LearningEvent

class LearningMigration:
    def __init__(self,learning):
        self.learning=learning
        if not learning.session_repository or not learning.progress_repository:
            raise ValueError('migration requires explicit session and facts repositories')
        self.repository=learning.session_repository
        self.engine=self.repository.engine

    def collect(self,owner,course):
        self.learning.require(course,owner)
        from .service import graph_leaves
        info=self.learning.manager.get_course_info(course)
        nodes=graph_leaves(self.learning.manager.get_knowledge_graph(course)) or [{'id':course,'title':info['title']}]
        sessions=[]
        for node in nodes:
            short=hashlib.sha256(node['id'].encode()).hexdigest()[:24]
            # Read the complete source, never load_or_empty's 100-turn projection.
            path=self.learning.manager.get_classroom_qa_dir(course,'learning_'+short,owner)/'session.json'
            if path.exists():
                value=json.loads(path.read_text())
                expected={'course_id':course,'owner_user_id':owner,'classroom_id':'learning_'+short}
                if any(k in value and value[k]!=v for k,v in expected.items()) or value.get('active_turn'):
                    raise ValueError('legacy source scope mismatch or active turn')
                sessions.append({'topic_id':node['id'],'session_id':value.get('session_id'),'turns':value.get('turns',[])})
        return {'owner':owner,'course_id':course,'sessions':sessions,'overlay':self.learning.store.get(owner,course),'source_kind':'live_store'}

    def scan(self,source):
        source=copy.deepcopy(source)
        owner,course=source['owner'],source['course_id']
        room=self.learning.room(course,owner,include_progress=False)
        topics={t['id'] for t in room['chapters']}
        refs={r['id']:(t['id'],r['remote']) for t in room['chapters'] for r in t['resources'] if r.get('remote')}
        unresolved=[];events=[];seen_topics=set();turn_count=0
        for session in source.get('sessions',[]):
            topic=session['topic_id']
            if topic not in topics or topic in seen_topics:
                raise ValueError('unknown or duplicate legacy topic')
            seen_topics.add(topic)
            seen=set()
            for i,turn in enumerate(session['turns']):
                if not isinstance(turn.get('question'),str) or not isinstance(turn.get('answer_text'),str):
                    raise ValueError('invalid legacy turn')
                key=str(turn.get('client_turn_id') or turn.get('turn_id') or f'legacy-{i}')
                if key in seen:
                    raise ValueError('duplicate legacy turn identifier')
                seen.add(key)
                turn_count+=1
            # Count is what exists, not an assertion that earlier data was never lost.
        overlay=source.get('overlay',{})
        for mid,state in overlay.get('progress',{}).items():
            if mid.startswith('pending:'):
                unresolved.append({'resource_id':mid,'reason':'placeholder_preserved','value':state})
                continue
            if mid not in refs:
                unresolved.append({'resource_id':mid,'reason':'orphan_resource','value':state})
                continue
            topic,remote=refs[mid]
            version=state.get('version')
            if type(version) is not int or version<1:
                unresolved.append({'resource_id':mid,'reason':'unknown_version','value':state})
                continue
            ref=ResourceRef(course_id=course,material_type=remote['materialType'],material_id=mid,version=version)
            try:
                from .resource_reader import exact_material
                exact_material(self.learning,owner,ref)
            except HTTPException:
                unresolved.append({'resource_id':mid,'reason':'unavailable_version','value':state})
                continue
            if type(state.get('completed')) is bool:
                events.append({'topic_id':topic,'type':'resource_completion_set','resource_ref':ref.model_dump(),
                    'expected_revision':0,'payload':{'completed':state['completed']}})
            if state.get('position') is not None or state.get('note'):
                unresolved.append({'resource_id':mid,'reason':'legacy_position_or_note_preserved','value':state})
        for topic,value in overlay.get('understanding',{}).items():
            if topic in topics and value in {'review','understood'}:
                events.append({'topic_id':topic,'type':'self_assessment_set','expected_revision':0,
                    'payload':{'value':'needs_review' if value=='review' else 'understood'}})
            else:
                unresolved.append({'topic_id':topic,'reason':'unknown_self_assessment','value':value})
        report={'schema_version':1,'scanned_at':datetime.now(timezone.utc).isoformat(),'source':source,'source_hash':digest(source),'counts':{'sessions':len(source.get('sessions',[])),'turns':turn_count},
            'events':events,'unresolved':unresolved,'history_completeness':'only surviving records; missing history is not reconstructed'}
        report['report_hash']=digest(report)
        return report

    @staticmethod
    def validate(report):
        if digest({k:v for k,v in report.items() if k!='report_hash'})!=report.get('report_hash') or digest(report['source'])!=report['source_hash']:
            raise ValueError('migration report changed')

    def import_records(self,report):
        self.validate(report)
        owner,course=report['source']['owner'],report['source']['course_id']
        self.learning.require(course,owner)
        # Input was reviewed; recheck current scope and exact versions before writing.
        current=self.scan(report['source'])
        if current['events']!=report['events']:
            raise ValueError('source references changed since scan')
        with self.repository._write('learning-migration:'+owner+':'+course) as db:
            ledger=db.get(Ledger,(owner,course))
            if ledger and ledger.source_hash!=report['source_hash']:
                raise ValueError('different source already imported; reconcile before changing it')
            if ledger and ledger.result.get('status')=='complete':
                check=self.reconcile(report)
                if check['unexplained_differences']:
                    raise ValueError('imported source no longer reconciles')
                return {'created':0,'total':ledger.result['total'],'unresolved':report['unresolved']}
            if ledger is not None:
                report=ledger.result['report']
            if ledger is None:
                db.add(Ledger(owner=owner,course_id=course,source_hash=report['source_hash'],source=report['source'],
                    result={'status':'importing','report':report},updated_at=time.time()))
        created=0
        for session in report['source'].get('sessions',[]):
            old=self.repository.find(owner,course,session['topic_id'])
            imported=self.repository.ensure_session(owner,course,session['topic_id'],'旧学习记录已保留，可以继续阅读或提问。',
                session['turns'],legacy_session_id=session.get('session_id'))
            if old is None:
                created+=imported['message_count']
        for index,item in enumerate(report['events']):
            event=LearningEvent(event_id=uuid5(NAMESPACE_URL,report['source_hash']+':'+str(index)),occurred_at=report['scanned_at'],
                **{k:v for k,v in item.items() if k!='topic_id'})
            with Session(self.engine) as db:
                existing=db.get(LearningEventRecord,(owner,str(event.event_id))) is not None
            # An explicit old version remains tied to that version. We deliberately
            # bypass current-manifest matching, after scan authorized exact storage.
            self.learning.progress_repository.record(owner,course,item['topic_id'],event)
            created+=not existing
        check=self.reconcile(report)
        if check['unexplained_differences']:
            raise ValueError('import reconciliation failed: '+json.dumps(check['unexplained_differences'],ensure_ascii=False))
        total=report['counts']['sessions']+report['counts']['turns']*2+len(report['events'])
        with self.repository._write('learning-migration:'+owner+':'+course) as db:
            ledger=db.get(Ledger,(owner,course))
            ledger.result={'status':'complete','total':total,'report':report,'reconciliation':check}
            ledger.updated_at=time.time()
        return {'created':created,'total':total,'unresolved':report['unresolved']}

    def reconcile(self,report):
        self.validate(report)
        owner,course=report['source']['owner'],report['source']['course_id']
        self.learning.require(course,owner)
        differences=[]
        with Session(self.engine) as db:
            ledger=db.get(Ledger,(owner,course))
            if ledger is None or ledger.source_hash!=report['source_hash'] or ledger.source!=report['source']:
                differences.append('source archive missing or changed')
            for source_session in report['source'].get('sessions',[]):
                sid=self.repository.identity(owner,course,source_session['topic_id'])
                session=db.get(LearningTopicSession,sid)
                if session is None:
                    differences.append({'topic_id':source_session['topic_id'],'reason':'missing_session'});continue
                if session.import_metadata.get('legacy_session_id')!=source_session.get('session_id'):
                    differences.append({'topic_id':source_session['topic_id'],'reason':'legacy_session_identity_mismatch'})
                history_sid=session.import_metadata.get('merged_into',sid)
                rows=list(db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==history_sid)))
                by_id={m.message_id:m for m in rows}
                for i,turn in enumerate(source_session['turns']):
                    key=str(turn.get('client_turn_id') or turn.get('turn_id') or f'legacy-{i}')
                    prefix=sid+':'+hashlib.sha256(key.encode()).hexdigest()+':'
                    for role,field in [('user','question'),('assistant','answer_text')]:
                        message=by_id.get(prefix+role)
                        if message is None or message.content!=turn[field] or message.raw_payload.get('legacy_turn_id')!=turn.get('turn_id'):
                            differences.append({'source_turn_id':key,'role':role,'reason':'missing_or_changed_message'})
            for index,item in enumerate(report['events']):
                eid=str(uuid5(NAMESPACE_URL,report['source_hash']+':'+str(index)))
                row=db.get(LearningEventRecord,(owner,eid))
                if row is None or row.topic_id!=item['topic_id'] or row.event['payload']!=item['payload']:
                    differences.append({'event_id':eid,'reason':'missing_or_changed_fact_receipt'})
        return {'source_hash':report['source_hash'],'unexplained_differences':differences,
            'preserved_unresolved':len(report['unresolved']),'surviving_turns':report['counts']['turns']}

    def archived(self,owner,course):
        self.learning.require(course,owner)
        with Session(self.engine) as db:
            ledger=db.get(Ledger,(owner,course))
            return copy.deepcopy(ledger.source) if ledger else None

    def activate(self,report,phase=5):
        if type(phase) is not int or not 1<=phase<=5:
            raise ValueError('invalid rollout phase')
        if self.reconcile(report)['unexplained_differences']:
            raise ValueError('reconcile before activating')
        owner,course=report['source']['owner'],report['source']['course_id']
        with self.repository._write('learning-migration:'+owner+':'+course) as db:
            # Detect in-flight legacy turns under the same lock used by their
            # begin/finish operations, and refuse stale live-store scans.
            current=self.collect(owner,course)
            if report['source'].get('source_kind')=='live_store' and digest(current)!=report['source_hash']:
                raise ValueError('legacy store changed since scan; do not activate')
            ledger=db.get(Ledger,(owner,course))
            if ledger.result.get('status')!='complete':
                raise ValueError('import incomplete')
            scope=db.get(Scope,(owner,course))
            if scope and phase<scope.phase:
                raise ValueError('facts cannot roll back to legacy storage; pause model features instead')
            if scope:
                scope.phase=phase
            else:
                db.add(Scope(owner=owner,course_id=course,phase=phase,source_hash=report['source_hash'],activated_at=time.time()))
        return {'owner':owner,'course_id':course,'phase':phase}
