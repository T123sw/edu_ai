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
