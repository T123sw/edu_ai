"""Read-only preparation view over the shared memory lifecycle."""
from sqlalchemy.orm import Session
from app.database.models import User
from app.chat.memory.lifecycle import MemoryLifecycle, MemoryChanged


class ContextRebuilt(RuntimeError): pass


class PreparationMemory:
    def __init__(self,repository):
        self.repository=repository
        self.lifecycle=MemoryLifecycle(repository.engine)

    def subject(self,owner):
        with Session(self.repository.engine) as session:
            user=session.get(User,owner)
            if user is None or user.is_disabled: raise PermissionError('OWNER_UNAVAILABLE')
            # Existing memory domain stores authenticated usernames. Preparation
            # authority remains immutable User.user_id; conversion is server-owned.
            return user.username

    @staticmethod
    def consumer(context): return 'preparation:'+context.preparation_id

    def prepare(self,context,checkpoint,request):
        subject=self.subject(context.owner_user_id)
        if 'memory_view' in checkpoint:
            self.validate(context,checkpoint)
            return checkpoint
        view=self.lifecycle.read_effective(subject,course_id=request.target.course_id if request.target else None)
        refs={v['memory_id']:v['revision'] for v in view['preferences'].values()}
        self.lifecycle.register_dependencies(subject,self.consumer(context),refs,expected_epoch=view['memory_epoch'])
        checkpoint={**checkpoint,'memory_view':view,'memory_subject':subject,'memory_refs':refs}
        self.repository.checkpoint(context,checkpoint)
        return checkpoint

    def validate(self,context,checkpoint):
        try: return self.lifecycle.validate_consumer(checkpoint['memory_subject'],self.consumer(context))
        except MemoryChanged:
            self.repository.restart_for_memory(context,checkpoint['memory_subject'])
            raise ContextRebuilt('MEMORY_DEPENDENT_CONTEXT_REBUILT')
