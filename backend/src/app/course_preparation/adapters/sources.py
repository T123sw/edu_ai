"""A source handle grants no authority: uploads are reauthorized on every read."""
from .documents import DocumentUnreadable


def upload_url(ref): return f'upload://{ref.document_id}/{ref.version}'


class PolicySources:
    def __init__(self, *, owner, request, documents, web):
        self.owner,self.request,self.documents,self.web=owner,request,documents,web
        self.uploads={upload_url(ref):ref for ref in request.uploads}

    def search(self,query,*,limit,timeout):
        if self.request.source_policy.mode=='uploaded_only':
            raise PermissionError('UPLOADED_ONLY_NETWORK_FORBIDDEN')
        return self.web.search(query,limit=limit,timeout=timeout)

    def read(self,url,*,timeout):
        if url in self.uploads:
            ref=self.uploads[url]
            parsed=self.documents.parse(self.owner,ref)
            if parsed['defects'] and ref.usage in ('primary','coverage'):
                raise DocumentUnreadable('CORE_SOURCE_UNREADABLE',parsed['defects'])
            return parsed['content']
        if self.request.source_policy.mode=='uploaded_only' or url.startswith('upload:'):
            raise PermissionError('SOURCE_OUTSIDE_SCOPE')
        return self.web.read(url,timeout=timeout)
