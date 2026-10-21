"""Allow narration, native repair passes and rendering to finish within a bounded job."""

CLASSROOM_GENERATION_TIMEOUT_SECONDS = 3600


def generation_limits(command):
    payload = dict(command)
    # Legacy classroom commands carry a five-minute deadline, including on retry.
    # Keep longer batch windows and start a separate execution window on claim.
    for key in ('deadline_seconds', 'execution_timeout_seconds'):
        payload[key] = max(CLASSROOM_GENERATION_TIMEOUT_SECONDS, int(payload.get(key) or 0))
    return payload
