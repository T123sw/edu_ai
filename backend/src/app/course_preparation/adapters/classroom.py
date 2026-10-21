"""Single classroom generation entry: native HyperFrames with measured narration."""
from app.integrations.hyperframes.generation import generate_classroom


def generate_classroom_draft(payload, *, gateway, context, artifact, checkpoint=None):
    return generate_classroom(payload, gateway=gateway, context=context, artifact=artifact, checkpoint=checkpoint)
