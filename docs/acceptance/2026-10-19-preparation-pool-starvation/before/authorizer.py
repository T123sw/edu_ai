"""Resolve every supplied reference using current server-side ownership."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User, Conversation, ConversationMessage


class PreparationReferenceAuthorizer:
    def __init__(self,engine,documents,*,targets=None):
        self.engine,self.documents,self.targets=engine,documents,targets

    def authorize(self,owner,request):
        with Session(self.engine) as session:
            user=session.get(User,owner)
            if user is None or user.is_disabled: raise PermissionError('OWNER_UNAVAILABLE')
            if request.origin:
                conversation=session.get(Conversation,request.origin.conversation_id)
                message=session.get(ConversationMessage,request.origin.message_id)
                if (conversation is None or conversation.owner != user.username
                        or message is None or message.conversation_id!=conversation.conversation_id):
                    raise PermissionError('ORIGIN_UNAVAILABLE')
        for ref in request.uploads:
            try: self.documents.authorize(owner,ref)
            except (LookupError,RuntimeError) as exc: raise PermissionError('SOURCE_UNAVAILABLE') from exc
        if request.target:
            if self.targets is None: raise PermissionError('TARGET_ADAPTER_UNAVAILABLE')
            self.targets.authorize(owner,request)
        if request.learning_context and (not request.target or self.targets is None):
            raise PermissionError('LEARNING_CONTEXT_UNAVAILABLE')
