"""A source handle grants no authority: uploads are reauthorized on every read."""
from .documents import DocumentUnreadable


def upload_url(ref): return f'upload://{ref.document_id}/{ref.version}'


class PolicySources:
    def __init__(self, *, owner, request, documents, web, snapshots=None, scope=None, parse=None):
        self.snapshots, self.scope, self.parse = snapshots, scope, parse
        self.owner,self.request,self.documents,self.web=owner,request,documents,web
        self.uploads={upload_url(ref):ref for ref in request.uploads}

    def capabilities(self):
        result=self.web.capabilities() if hasattr(self.web, "capabilities") else {}
        return {**result,"source_policy":self.request.source_policy.mode}

    def search(self,query,*,limit,timeout):
        if self.scope: self.scope.check()
        if self.request.source_policy.mode=='uploaded_only':
            raise PermissionError('UPLOADED_ONLY_NETWORK_FORBIDDEN')
        return self.web.search(query,limit=limit,timeout=timeout)

    def read(self,url,*,timeout):
        if url in self.uploads:
            ref=self.uploads[url]
            parsed=self.parse(ref) if self.parse else self.documents.parse(self.owner,ref)
            if parsed['defects'] and ref.usage in ('auto','primary','coverage'):
                raise DocumentUnreadable('CORE_SOURCE_UNREADABLE',parsed['defects'])
            return parsed['content']
        if self.request.source_policy.mode=='uploaded_only' or url.startswith('upload:'):
            raise PermissionError('SOURCE_OUTSIDE_SCOPE')
        return self.read_snapshot(url,timeout=timeout).content if self.snapshots else self.web.read(url,timeout=timeout)

    def read_snapshot(self,url,*,timeout):
        if url.startswith('upload:'):
            return None
        if self.request.source_policy.mode=='uploaded_only':
            raise PermissionError('SOURCE_OUTSIDE_SCOPE')
        if not self.snapshots:
            return None
        reader=getattr(self.web,'read_body',self.web.read)
        return self.snapshots.get_or_fetch(url,read=reader,scope=self.scope,timeout=timeout)

    def authorize_read(self,url):
        if url in self.uploads:
            if self.scope: self.scope.guard()
            self.documents.authorize(self.owner,self.uploads[url])
        elif url.startswith('upload:') or self.request.source_policy.mode=='uploaded_only':
            raise PermissionError('SOURCE_OUTSIDE_SCOPE')
        elif self.scope:
            self.scope.check()
