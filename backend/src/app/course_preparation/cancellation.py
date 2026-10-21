"""Cancel only this preparation's queue work, in the parent transaction."""
from sqlalchemy import select
from app.database.models import DurableTaskModel


def cancel_preparation_tasks(session, owner, preparation_id, now):
    tasks = session.scalars(select(DurableTaskModel).where(
        DurableTaskModel.owner_user_id == owner,
        DurableTaskModel.scope_type == 'preparation',
        DurableTaskModel.scope_id == preparation_id,
        DurableTaskModel.workflow_type.in_(('preparation_step', 'preparation_resource')),
        DurableTaskModel.status.in_(('pending', 'leased')),
    ).order_by(DurableTaskModel.task_id).with_for_update()).all()
    for task in tasks:
        task.cancel_requested = True
        task.error_code = 'GENERATION_CANCELLED'
        task.error = 'Course preparation was canceled'
        task.updated_at = now
        if task.status == 'pending':
            task.status = 'canceled'
            task.finished_at = now
        # A leased task keeps its lease until the worker releases processes and
        # settles in-flight usage. Its guard sees cancel_requested immediately.
