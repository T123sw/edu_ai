"""Bounded dynamic batching of independent, complete speech requests."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable


def bound_waveform_decode(model):
    """Keep GPU token generation batched, decode each complete waveform separately.

    The SDK pads all audio codes before waveform decoding. Long chapters can
    otherwise multiply decoder memory by the full inference batch size.
    """
    tokenizer = model.model.speech_tokenizer
    original = tokenizer.decode
    def decode(encoded):
        if not isinstance(encoded, list) or len(encoded) <= 1:
            return original(encoded)
        outputs, sample_rate = [], None
        for utterance in encoded:
            wavs, rate = original([utterance])
            if len(wavs) != 1 or (sample_rate is not None and rate != sample_rate):
                raise RuntimeError('waveform decoding output mismatch')
            outputs.extend(wavs)
            sample_rate = rate
        return outputs, sample_rate
    tokenizer.decode = decode


@dataclass
class Entry:
    value: Any
    future: asyncio.Future


class SpeechBatchQueue:
    def __init__(self, processor: Callable, *, max_batch=4, max_pending=64,
                 batch_window=.1, max_chars=1600, length=lambda value: len(value[0].input)):
        self.processor = processor
        self.max_batch, self.batch_window, self.max_chars = max_batch, batch_window, max_chars
        self.length = length
        self.queue = asyncio.Queue(maxsize=max_pending)
        self.runner = None
        self.active = 0
        self.carry = None

    async def submit(self, value):
        if self.runner is None:
            self.runner = asyncio.create_task(self._run())
        future = asyncio.get_running_loop().create_future()
        self.queue.put_nowait(Entry(value, future))
        return await future

    async def close(self):
        await self.queue.join()
        if self.runner is not None:
            self.runner.cancel()
            try:
                await self.runner
            except asyncio.CancelledError:
                pass
            self.runner = None

    @property
    def pending(self):
        return self.queue.qsize() + int(self.carry is not None)

    async def _run(self):
        while True:
            first = self.carry
            self.carry = None
            if first is None:
                first = await self.queue.get()
            if first.future.cancelled():
                self.queue.task_done()
                continue
            batch = [first]
            chars = self.length(first.value)
            await asyncio.sleep(self.batch_window)
            while len(batch) < self.max_batch:
                try:
                    item = self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item.future.cancelled():
                    self.queue.task_done()
                    continue
                if chars + self.length(item.value) > self.max_chars:
                    self.carry = item
                    break
                batch.append(item)
                chars += self.length(item.value)
            ready = []
            for item in batch:
                if item.future.cancelled():
                    self.queue.task_done()
                else:
                    ready.append(item)
            batch = ready
            if not batch:
                continue
            self.active = len(batch)
            try:
                results = await asyncio.to_thread(self.processor, [item.value for item in batch])
                if len(results) != len(batch):
                    raise RuntimeError('speech batch output count mismatch')
            except Exception as exc:
                results = [exc] * len(batch)
            finally:
                self.active = 0
            for item, result in zip(batch, results):
                if not item.future.done():
                    if isinstance(result, Exception):
                        item.future.set_exception(result)
                    else:
                        item.future.set_result(result)
                self.queue.task_done()
