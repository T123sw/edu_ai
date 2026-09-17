"""Auditable legacy import: scan first, preserve unknown versions without inventing facts."""
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import ConversationMessage
from .db_models import LearningTopicSession


class LearningImporter:
    def __init__(self,repository): self.repository=repository

    @staticmethod
    def scan(source):
        source=Path(source).resolve()
        data=json.loads(source.read_text())
        if not isinstance(data,dict) or not isinstance(data.get('sessions'),list): raise ValueError('sessions manifest required')
        sessions=[]; conflicts=[]
        identities=set()
        for entry in data['sessions']:
            identity=tuple(entry.get(k,'') for k in ('owner','course_id','topic_id'))
            if not all(isinstance(v,str) and v for v in identity) or identity in identities:
                conflicts.append({'entry':identity,'reason':'invalid_or_duplicate_scope'}); continue
            identities.add(identity)
            path=(source.parent/entry['path']).resolve()
            if not path.is_relative_to(source.parent): raise ValueError('legacy path escapes source directory')
            raw=path.read_bytes(); payload=json.loads(raw)
            turns=payload.get('turns',[])
            if payload.get('active_turn') or not isinstance(turns,list):
                conflicts.append({'entry':identity,'reason':'active_or_invalid_session'}); continue
            if payload.get('owner_user_id',identity[0])!=identity[0] or payload.get('course_id',identity[1])!=identity[1]:
                conflicts.append({'entry':identity,'reason':'source_scope_mismatch'}); continue
            ids=[t.get('client_turn_id') or t.get('turn_id') for t in turns]
            if any(not i for i in ids) or len(ids)!=len(set(ids)) or any(not isinstance(t.get('question'),str) or not isinstance(t.get('answer_text'),str) for t in turns):
                conflicts.append({'entry':identity,'reason':'invalid_or_duplicate_turn'}); continue
            sessions.append({'owner':identity[0],'course_id':identity[1],'topic_id':identity[2],
                'path':str(path),'source_sha256':hashlib.sha256(raw).hexdigest(),'turn_count':len(turns),
                'legacy_session_id':payload.get('session_id'),'turn_ids':ids})
        return {'schema_version':1,'source':str(source),'sessions':sessions,'conflicts':conflicts,
            'unversioned_progress':data.get('unversioned_progress',[]),
            'orphan_resources':data.get('orphan_resources',[]),'placeholder_notes':data.get('placeholder_notes',[]),
            'limitations':['仅导入源文件实际保留的历史；未保留历史不补造。','无准确资源版本的旧完成标记保留在审计报告中，不绑定当前版本。']}

    def import_records(self,report):
        if report['conflicts']: raise ValueError('Resolve scan conflicts before import')
        created=0
        for item in report['sessions']:
            raw=Path(item['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item['source_sha256']: raise ValueError('SOURCE_CHANGED_AFTER_SCAN')
            before=self.repository.find(item['owner'],item['course_id'],item['topic_id'])
            if before:
                with Session(self.repository.engine) as db:
                    row=db.get(LearningTopicSession,before['session_id'])
                    source_digest=hashlib.sha256(json.dumps(json.loads(raw)['turns'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    if row.import_metadata.get('turn_count')!=item['turn_count'] or row.import_metadata.get('source_sha256')!=source_digest:
                        raise ValueError('EXISTING_SESSION_REQUIRES_RECONCILIATION')
            value=self.repository.ensure_session(item['owner'],item['course_id'],item['topic_id'],'可以继续阅读，也可以随时提问。',
                json.loads(raw)['turns'],legacy_session_id=item['legacy_session_id'])
            created+=int(before is None)
        return {'created':created,'total':len(report['sessions']),'reconciliation':self.reconcile(report)}

    def reconcile(self,report):
        differences=[]; counts=[]
        for item in report['sessions']:
            session=self.repository.find(item['owner'],item['course_id'],item['topic_id'])
            if session is None:
                differences.append({'path':item['path'],'reason':'session_missing'}); continue
            with Session(self.repository.engine) as db:
                rows=db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==session['session_id'])).all()
                imported=[r for r in rows if r.raw_payload.get('source')=='legacy']
                ids={r.raw_payload['request_id'] for r in imported}
                if len(imported)!=item['turn_count']*2 or ids!=set(item['turn_ids']): differences.append({'path':item['path'],'reason':'history_count_or_ids_differ'})
                original=json.loads(Path(item['path']).read_text())['turns']
                expected={(str(t.get('client_turn_id') or t['turn_id']),role):t[key] for t in original for role,key in [('user','question'),('assistant','answer_text')]}
                if any(expected.get((r.raw_payload['request_id'],r.role))!=r.content for r in imported): differences.append({'path':item['path'],'reason':'history_content_differs'})
                counts.append({'session_id':session['session_id'],'source_turns':item['turn_count'],'imported_messages':len(imported)})
        return {'unexplained_differences':differences,'counts':counts}
