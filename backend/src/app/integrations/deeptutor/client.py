from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import AsyncIterator
from urllib.parse import quote, urlparse

import httpx


class DeepTutorError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class DeepTutorConfig:
    base_url: str
    token: str = field(repr=False)
    connect_timeout: float = 10
    read_timeout: float = 180

    def __post_init__(self):
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("DeepTutor requires a configured service origin")
        if len(self.token) < 32:
            raise ValueError("DeepTutor service token is missing or too short")


class DeepTutorClient:
    def __init__(self, config: DeepTutorConfig, *, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self.http = httpx.AsyncClient(base_url=config.base_url.rstrip("/"), trust_env=False,
                                     follow_redirects=False, transport=transport,
                                     timeout=httpx.Timeout(config.read_timeout, connect=config.connect_timeout))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.http.aclose()

    def _headers(self, owner: str) -> dict:
        if not owner.strip() or len(owner) > 255 or "\n" in owner or "\r" in owner:
            raise ValueError("Trusted owner identity required")
        return {"Authorization": "Bearer " + self.config.token, "X-Edu-Owner": quote(owner, safe="")}

    @staticmethod
    def _check(response: httpx.Response):
        if not 200 <= response.status_code < 300:
            # Never propagate upstream prompt/error text or auth material.
            raise DeepTutorError(response.status_code, "DeepTutor request was not accepted")

    async def _request(self, method: str, path: str, *, owner: str, **kwargs) -> dict:
        try:
            response = await self.http.request(method, path, headers=self._headers(owner), **kwargs)
            self._check(response)
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Unexpected response shape")
            return data
        except httpx.TransportError:
            raise DeepTutorError(503, "DeepTutor service unavailable") from None
        except (ValueError, json.JSONDecodeError):
            raise DeepTutorError(502, "Invalid DeepTutor response") from None

    async def start(self, *, owner: str, request: dict) -> dict:
        # Caller persists request_id; retrying transport uses that same id.
        return await self._request("POST", "/internal/generations", owner=owner, json=request)

    async def status(self, *, owner: str, turn_id: str) -> dict:
        return await self._request("GET", f"/internal/turns/{quote(turn_id, safe='')}", owner=owner)

    async def cancel(self, *, owner: str, turn_id: str) -> dict:
        return await self._request("POST", f"/internal/turns/{quote(turn_id, safe='')}/cancel", owner=owner)

    async def _events(self, *, owner: str, turn_id: str, after_seq: int, view: str) -> AsyncIterator[dict]:
        if after_seq < 0:
            raise ValueError("Event cursor must be nonnegative")
        try:
            async with self.http.stream("GET", f"/internal/turns/{quote(turn_id, safe='')}/events",
                                        params={"after_seq": after_seq, "view": view}, headers=self._headers(owner)) as response:
                self._check(response)
                async for line in response.aiter_lines():
                    if line.strip():
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("Unexpected event shape")
                        yield event
        except httpx.TransportError:
            raise DeepTutorError(503, "DeepTutor event connection interrupted") from None
        except (ValueError, json.JSONDecodeError):
            raise DeepTutorError(502, "Invalid DeepTutor event") from None

    def progress(self, *, owner: str, turn_id: str, after_seq: int = 0):
        return self._events(owner=owner, turn_id=turn_id, after_seq=after_seq, view="progress")

    def internal_events(self, *, owner: str, turn_id: str, after_seq: int = 0):
        """Server-side persistence only: contains answers, templates and tool traces."""
        return self._events(owner=owner, turn_id=turn_id, after_seq=after_seq, view="internal")
