"""Bind a real source byte hash to a server-owned monotonically versioned upload."""
from dataclasses import asdict
import hashlib
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User, PreparationDocumentVersion as Version
from .documents import DocumentParser, DocumentUnreadable


def _legacy_parse(parsed):
    return parsed is not None and parsed.get('parser') in {
        'antiword-text-v1', 'rag-docx-text-v1', 'libreoffice+rag-docx-text-v1',
    }


class DocumentStore:
    def __init__(self, engine, reader, parser=None):
        self.engine, self.reader, self.parser = engine, reader, parser or DocumentParser()

    @staticmethod
    def _username(session, owner):
        user=session.get(User,owner)
        if user is None or user.is_disabled: raise PermissionError('OWNER_UNAVAILABLE')
        return user.username

    def register(self, owner, document_id):
        with Session(self.engine) as session, session.begin():
            session.scalar(select(User).where(User.user_id==owner).with_for_update())
            username=self._username(session,owner)
            record,data=self.reader.read_bytes(username,document_id)
            digest=hashlib.sha256(data).hexdigest()
            latest=session.scalar(select(Version).where(Version.owner_user_id==owner,Version.document_id==document_id)
                .order_by(Version.version.desc()).limit(1))
            if latest and latest.content_sha256==digest:
                return {'document_id':document_id,'version':latest.version}
            version=1 if latest is None else latest.version+1
            session.add(Version(owner_user_id=owner,document_id=document_id,version=version,
                content_sha256=digest,filename=str(record['filename'])))
            return {'document_id':document_id,'version':version}

    def authorize(self,owner,ref):
        with Session(self.engine) as session:
            row=session.get(Version,(owner,ref.document_id,ref.version))
            if row is None: raise PermissionError('DOCUMENT_VERSION_UNAVAILABLE')
            _,data=self.reader.read_bytes(self._username(session,owner),ref.document_id)
            if hashlib.sha256(data).hexdigest()!=row.content_sha256:
                raise PermissionError('DOCUMENT_VERSION_CHANGED')
            return {'filename':row.filename,'content_sha256':row.content_sha256}

    def parse(self,owner,ref):
        self.authorize(owner,ref)
        with Session(self.engine) as session:
            row=session.get(Version,(owner,ref.document_id,ref.version))
            if row.parsed is not None and not _legacy_parse(row.parsed): return dict(row.parsed)
            filename,digest,username=row.filename,row.content_sha256,self._username(session,owner)
        _,data=self.reader.read_bytes(username,ref.document_id)
        if hashlib.sha256(data).hexdigest()!=digest: raise PermissionError('DOCUMENT_VERSION_CHANGED')
        result=asdict(self.parser.parse(data,filename=filename))
        self.authorize(owner,ref)
        with Session(self.engine) as session, session.begin():
            row=session.get(Version,(owner,ref.document_id,ref.version))
            if row is None: raise PermissionError('DOCUMENT_VERSION_UNAVAILABLE')
            if row.parsed is None or _legacy_parse(row.parsed): row.parsed=result
            return dict(row.parsed)

    def read(self,owner,ref,*,offset=0,limit=4000):
        if offset<0 or limit<1 or limit>5000: raise ValueError('INVALID_DOCUMENT_WINDOW')
        parsed=self.parse(owner,ref)
        if parsed['defects'] and ref.usage in ('auto','primary','coverage'):
            raise DocumentUnreadable('CORE_SOURCE_UNREADABLE',parsed['defects'])
        content=parsed['content']
        if offset>=len(content): raise ValueError('DOCUMENT_OFFSET_OUT_OF_RANGE')
        return {'content':content[offset:offset+limit], 'offset_chars':offset,
            'next_offset':offset+limit if offset+limit<len(content) else None,
            'source_hash':parsed['source_hash'],'parser':parsed['parser'],'defects':parsed['defects']}
