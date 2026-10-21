from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import torch

from services.local_tts.voice_profile import (
    RequestSampler, bind_request_sampling, request_sampling,
)


def sequence(seeds, steps=30):
    sampler = RequestSampler(seeds)
    scores = torch.linspace(-1, 1, 100).repeat(len(seeds), 1)
    return torch.stack([sampler(None, scores).argmax(-1) for _ in range(steps)])


def test_voice_sampling_is_independent_of_batch_order_and_peers():
    alone = sequence([17])[:, 0]
    batch = sequence([9, 17, 21])
    reordered = sequence([21, 9, 17])
    assert torch.equal(alone, batch[:, 1])
    assert torch.equal(alone, reordered[:, 2])
    assert torch.equal(batch[:, 0], reordered[:, 1])
    assert not torch.equal(batch[:, 0], batch[:, 1])


def test_sampler_preserves_global_rng_and_never_selects_forbidden_tokens():
    before = torch.get_rng_state().clone()
    sampler = RequestSampler([5])
    scores = torch.tensor([[-torch.inf, 1., 2., -torch.inf]])
    for _ in range(20):
        result = sampler(None, scores)
        assert result.argmax().item() in {1, 2}
        assert torch.isfinite(result).sum() == 1
    assert torch.equal(before, torch.get_rng_state())


def test_request_sampler_attaches_to_actual_talker_and_restores_context():
    model = SimpleNamespace(model=SimpleNamespace(talker=SimpleNamespace(generate=lambda **kw:kw)))
    bind_request_sampling(model)
    def execute(key):
        with request_sampling([key]):
            return model.model.talker.generate(do_sample=True)['logits_processor'][0].seeds
    with ThreadPoolExecutor(max_workers=3) as pool:
        a, b, again = list(pool.map(execute, ['same', 'different', 'same']))
    assert a == again and a != b
    assert 'logits_processor' not in model.model.talker.generate(do_sample=True)
    try:
        with request_sampling(['error']):
            raise ValueError('intentional')
    except ValueError:
        pass
    assert 'logits_processor' not in model.model.talker.generate(do_sample=True)
