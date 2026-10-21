"""Resolve every supplied reference using current server-side ownership."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User, Conversation, ConversationMessage


class PreparationReferenceAuthorizer:
    def __init__(self,engine,documents,*,targets=None):
        self.engine,self.documents,self.targets=engine,documents,targets

    def authorize(self,owner,request):
        with Session(self.engine) as session:
            return self.authorize_in_session(session,owner,request)

    def authorize_in_session(self,session,owner,request):
        # A caller may hold the preparation/memory locks. Reuse its connection:
        # acquiring another from the same pool can strand the lock holder when
        # all remaining connections are occupied by callers waiting for its lock.
        user=session.get(User,owner,populate_existing=True)
        if user is None or user.is_disabled: raise PermissionError('OWNER_UNAVAILABLE')
        if request.origin:
            conversation=session.get(Conversation,request.origin.conversation_id,populate_existing=True)
            message=session.get(ConversationMessage,request.origin.message_id,populate_existing=True)
            if (conversation is None or conversation.owner != user.username
                    or message is None or message.conversation_id!=conversation.conversation_id):
                raise PermissionError('ORIGIN_UNAVAILABLE')
        for ref in request.uploads:
            try:
                authorize=getattr(self.documents,'authorize_in_session',None)
                if authorize is not None: authorize(session,owner,ref)
                else: self.documents.authorize(owner,ref)
            except (LookupError,RuntimeError) as exc: raise PermissionError('SOURCE_UNAVAILABLE') from exc
        if request.target:
            if self.targets is None: raise PermissionError('TARGET_ADAPTER_UNAVAILABLE')
            authorize=getattr(self.targets,'authorize_in_session',None)
            if authorize is not None: authorize(session,owner,request)
            else: self.targets.authorize(owner,request)
        if request.learning_context and (not request.target or self.targets is None):
            raise PermissionError('LEARNING_CONTEXT_UNAVAILABLE')
