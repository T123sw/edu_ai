from sqlalchemy.orm import Session
from app.database import Base
from app.self_learning.notifications import NotificationService
from app.self_learning.db_models import LearningNotification
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation


def test_delivery_notification_is_deduplicated_separate_and_owner_scoped(ready):
    repo,context,delivery=ready
    Base.metadata.create_all(repo.engine,tables=[LearningNotification.__table__])
    receipt=delivery.commit(context)
    notifications=NotificationService(repo.engine)
    assert notifications.consume()==1
    assert notifications.consume()==0
    items=notifications.list('alice')
    assert len(items)==1 and items[0]['result_ref']==receipt.result_ref
    assert notifications.list('bob')==[]
    notifications.mark_read('alice',items[0]['event_id'])
    assert notifications.list('alice')[0]['read']
