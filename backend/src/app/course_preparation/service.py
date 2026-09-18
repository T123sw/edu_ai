"""Small authenticated application service; source authorization stays server-side."""
class PreparationService:
    def __init__(self, repository, *, wake=lambda _: None):
        self.repository, self.wake = repository, wake

    def submit(self, owner, request, **options):
        if 'config_snapshot' not in options:
            snapshot = getattr(self, 'snapshot_factory', None)
            if snapshot: options['config_snapshot'] = snapshot(owner)
        value = self.repository.submit(owner, request, **options)
        self.wake(value['preparation_id'])
        return value

    def get(self, owner, preparation_id):
        return self.repository.get_public(owner, preparation_id)

    def cancel(self, owner, preparation_id, expected_revision=None):
        return self.repository.cancel(owner, preparation_id, expected_revision=expected_revision)

    def retry(self, owner, preparation_id):
        value = self.repository.retry(owner, preparation_id)
        self.wake(preparation_id)
        return value

    def events(self, owner, preparation_id, after=0):
        return self.repository.events(owner_user_id=owner, preparation_id=preparation_id, after=after)

    def list(self, owner, limit=50):
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from app.database.models import CoursePreparationRecord, PreparationExecution
        with Session(self.repository.engine) as session:
            ids = list(session.scalars(select(CoursePreparationRecord.preparation_id).join(PreparationExecution,
                (PreparationExecution.preparation_id == CoursePreparationRecord.preparation_id) &
                (PreparationExecution.attempt_no == CoursePreparationRecord.current_attempt_no)).where(
                CoursePreparationRecord.owner_user_id == owner).order_by(CoursePreparationRecord.created_at.desc()).limit(limit)))
        return [self.get(owner, pid) for pid in ids]

    def intermediates(self, owner, preparation_id):
        from sqlalchemy.orm import Session
        from app.database.models import PreparationExecution
        public = self.get(owner, preparation_id)
        with Session(self.repository.engine) as session:
            run = session.get(PreparationExecution, (preparation_id, public['attempt_no']))
            checkpoint = run.checkpoint if run else {}
            return {key: checkpoint[key] for key in ('brief', 'input_documents', 'research_summary', 'plan', 'node_evidence', 'quality', 'candidate_manifest') if key in checkpoint}
