"""Historical OpenMAIC data helper; new generation is exclusively HyperFrames."""
from ..tool_registry import digest


def model_view(value):
    """Keep generated binary media out of text-model context, retaining identity."""
    if isinstance(value, str) and value.startswith('data:'):
        return '[embedded media sha256=' + digest(value) + ']'
    if isinstance(value, dict):
        return {k: model_view(v) for k, v in value.items()}
    if isinstance(value, list):
        return [model_view(v) for v in value]
    return value


def run_native(*args, **kwargs):
    raise RuntimeError('OPENMAIC_GENERATION_RETIRED: use adapters.classroom.generate_classroom_draft')


generate_native_draft = run_native
