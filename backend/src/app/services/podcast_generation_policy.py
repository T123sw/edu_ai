"""Give whole-utterance podcast synthesis a separate, bounded execution window."""

PODCAST_GENERATION_TIMEOUT_SECONDS = 7200


def generation_limits(command):
    payload = dict(command)
    for key in ('deadline_seconds', 'execution_timeout_seconds'):
        payload[key] = max(PODCAST_GENERATION_TIMEOUT_SECONDS, int(payload.get(key) or 0))
    return payload
