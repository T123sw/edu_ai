"""Task-pinned immutable bodies, stored in the existing durable SQL checkpoint.

No global cache or new authority: validate the live scope before EVERY hit. A task
pins a version until its checkpoint is deleted; explicit expiry fails closed and
never overwrites evidence. Callers must persist the backing dictionary atomically.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from .research_sources import public_url
from .research_agent import ResearchError, RecoverableSourceError


@dataclass(frozen=True)
class SnapshotScope:
    owner: str
    preparation: str
    source_policy: str
    config_version: str
    guard: object
    expires_at: str | None = None

    def identity(self):
        return {k:getattr(self,k) for k in ('owner','preparation','source_policy','config_version')}

    def check(self):
        self.guard()
        if self.source_policy == 'uploaded_only':
            raise PermissionError('UPLOADED_ONLY_NETWORK_FORBIDDEN')
        if self.expires_at and datetime.now(timezone.utc) >= datetime.fromisoformat(self.expires_at):
            raise ResearchError('SNAPSHOT_EXPIRED','任务正文快照已过期；原证据仍保留，不刷新覆盖')


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_id: str
    canonical_url: str
    content: str
    content_sha256: str
    retrieved_at: str


class SourceSnapshots:
    def __init__(self, records=None, *, persist=None):
        self.records = records if records is not None else {}
        self.persist = persist or (lambda: None)

    @staticmethod
    def key(scope, url):
        return hashlib.sha256(json.dumps([scope.identity(),url],sort_keys=True).encode()).hexdigest()

    def get_or_fetch(self, url, *, read, scope, timeout):
        scope.check()
        url=public_url(url)
        key=self.key(scope,url)
        if key in self.records:
            return self._validated(self.records[key])
        if timeout <= 0:
            raise ResearchError('DEADLINE_EXCEEDED','来源读取预算已耗尽')
        result=read(url,timeout=timeout)
        scope.check()
        canonical=public_url(result['canonical_url']) if isinstance(result,dict) else url
        content=result['content'] if isinstance(result,dict) else result
        if not isinstance(content,str) or len(content.strip())<100:
            raise RecoverableSourceError('EXTRACT_NO_BODY','未取得有效正文，搜索摘要不能作为证据')
        canonical_key=self.key(scope,canonical)
        if canonical_key in self.records:
            snapshot=self._validated(self.records[canonical_key])
        else:
            digest=hashlib.sha256(content.encode()).hexdigest()
            snapshot=SourceSnapshot('snapshot_'+hashlib.sha256((canonical_key+digest).encode()).hexdigest()[:24],
                canonical,content,digest,datetime.now(timezone.utc).isoformat())
        previous=dict(self.records)
        self.records[key]=asdict(snapshot)
        self.records[canonical_key]=asdict(snapshot)
        try:
            scope.check()
            self.persist()
        except Exception:
            self.records.clear(); self.records.update(previous)
            raise
        return snapshot

    @staticmethod
    def _validated(record):
        result=SourceSnapshot(**record)
        if hashlib.sha256(result.content.encode()).hexdigest()!=result.content_sha256:
            raise ResearchError('SNAPSHOT_CORRUPT','正文快照哈希不匹配')
        return result
