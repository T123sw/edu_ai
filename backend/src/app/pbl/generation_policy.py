"""Bounded queue and execution windows for multi-call project generation."""
PBL_GENERATION_TIMEOUT_SECONDS = 1800


def generation_limits(command):
    payload=dict(command)
    payload.setdefault('deadline_seconds',PBL_GENERATION_TIMEOUT_SECONDS)
    payload.setdefault('execution_timeout_seconds',PBL_GENERATION_TIMEOUT_SECONDS)
    return payload
