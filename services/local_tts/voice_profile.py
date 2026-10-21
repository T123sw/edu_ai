"""Versioned narration style shared by every request to the local voice service."""

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib

import torch
from transformers import LogitsProcessor, LogitsProcessorList

VOICE_PROFILE = "stable-narration-v1"
VOICE_INSTRUCTIONS = (
    "使用所选说话人本人的自然音色，以平稳、清晰的语气进行教学讲解。"
    "保持一致的中等音高和发声位置，音量均匀、语气平和。"
    "只朗读输入文字，不模仿角色，不改变声线，不突然提高或压低音调，"
    "不使用夸张情绪。保留自然的句末语调和停顿。"
)
# The main talker uses the request-local sampler below; the acoustic sub-talker
# is greedy. Pure greedy main-talker decoding failed the real-model time gate.
GENERATION_OPTIONS = {
    "do_sample": False,
    "subtalker_dosample": False,
    "temperature": 1.0,
    "top_p": 1.0,
    "top_k": 0,
    "subtalker_temperature": 1.0,
    "subtalker_top_p": 1.0,
    "subtalker_top_k": 0,
}

_request_seeds = ContextVar('narration_request_seeds', default=None)


@contextmanager
def request_sampling(keys):
    seeds = [int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big') % (2**63 - 1)
             for key in keys]
    token = _request_seeds.set(seeds)
    try:
        yield
    finally:
        _request_seeds.reset(token)


class RequestSampler(LogitsProcessor):
    """Independent random streams, invariant to queue order and peer lengths.

    Transformers calls this after its repetition and forbidden-token processors.
    It samples one token per request, then leaves only that token for argmax.
    No global RNG is reset, and the model still processes the whole GPU batch.
    """
    def __init__(self, seeds, *, temperature=.65, top_k=30, top_p=.9):
        self.seeds = seeds
        self.temperature, self.top_k, self.top_p = temperature, top_k, top_p
        self.generators = None

    def __call__(self, input_ids, scores):
        if scores.shape[0] != len(self.seeds):
            raise RuntimeError('narration sampler batch size mismatch')
        if self.generators is None:
            self.generators = [torch.Generator(device=scores.device).manual_seed(seed)
                               for seed in self.seeds]
        values, indices = torch.topk(scores.float() / self.temperature,
                                    min(self.top_k, scores.shape[-1]), dim=-1)
        probabilities = torch.softmax(values, dim=-1)
        remove = probabilities.cumsum(dim=-1) - probabilities >= self.top_p
        probabilities = probabilities.masked_fill(remove, 0)
        selected = [torch.multinomial(row, 1, generator=generator)
                    for row, generator in zip(probabilities, self.generators)]
        chosen = indices.gather(1, torch.stack(selected))
        return torch.full_like(scores, -torch.inf).scatter_(1, chosen, 0)


def bind_request_sampling(model):
    # Qwen's wrapper currently drops arbitrary generate kwargs. Attach at the
    # actual talker boundary, without changing the installed SDK or global RNG.
    talker = model.model.talker
    original = talker.generate

    def generate(*args, **kwargs):
        seeds = _request_seeds.get()
        if seeds is not None:
            processors = list(kwargs.get('logits_processor') or [])
            kwargs['logits_processor'] = LogitsProcessorList(processors + [RequestSampler(seeds)])
            kwargs['do_sample'] = False
        return original(*args, **kwargs)

    talker.generate = generate
