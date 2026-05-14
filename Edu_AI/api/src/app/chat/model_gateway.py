from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import json
import time

import requests


class ChatModelGateway:
    """Unified OpenAI-compatible chat/completions gateway with fallback providers."""

    def __init__(
        self,
        *,
        api_base: str,
        api_key: Optional[str],
        model_name: str,
        fallbacks: Optional[List[Dict[str, Any]]] = None,
    ):
        primary = self._normalize_candidate(
            {
                "api_base": api_base,
                "api_key": api_key,
                "model_name": model_name,
            }
        )
        self.api_base = primary["api_base"]
        self.api_key = primary["api_key"]
        self.model_name = primary["model_name"]
        self.candidates: List[Dict[str, Any]] = [primary]
        for fallback in fallbacks or []:
            candidate = self._normalize_candidate(fallback)
            if any(
                existing["api_base"] == candidate["api_base"]
                and existing["model_name"] == candidate["model_name"]
                for existing in self.candidates
            ):
                continue
            self.candidates.append(candidate)

    @staticmethod
    def _normalize_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
        base = str(candidate.get("api_base") or "").rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return {
            "api_base": base,
            "api_key": candidate.get("api_key"),
            "model_name": candidate.get("model_name"),
        }

    @staticmethod
    def _build_headers(api_key: Optional[str]) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _thinking_params(model_name: str) -> Dict[str, Any]:
        # Qwen3 family enables chain-of-thought thinking by default, causing ~85s TTFT.
        # Disable it for chat use cases where reasoning transparency isn't needed.
        if str(model_name or "").lower().startswith("qwen3"):
            return {"enable_thinking": False}
        return {}

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1200) -> str:
        errors: List[str] = []
        for candidate in self.candidates:
            url = f"{candidate['api_base']}/chat/completions"
            payload: Dict[str, Any] = {
                "model": candidate["model_name"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **self._thinking_params(candidate["model_name"]),
            }
            t0 = time.perf_counter()
            try:
                resp = requests.post(
                    url,
                    headers=self._build_headers(candidate.get("api_key")),
                    json=payload,
                    timeout=120,
                )
            except requests.RequestException as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                print(f"[LLM] ✗ {candidate['model_name']} 同步调用失败 {elapsed_ms:.0f}ms | {exc}", flush=True)
                errors.append(f"{candidate['model_name']}: {exc}")
                continue
            if resp.status_code != 200:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                print(f"[LLM] ✗ {candidate['model_name']} HTTP {resp.status_code} {elapsed_ms:.0f}ms", flush=True)
                errors.append(f"{candidate['model_name']}: {resp.status_code} {resp.text}")
                continue

            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"[LLM] ✓ {candidate['model_name']} 同步调用 {elapsed_ms:.0f}ms | {len(content)} 字符", flush=True)
            return content

        raise RuntimeError(f"模型调用失败: {' | '.join(errors)}")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> Iterable[str]:
        errors: List[str] = []
        for candidate in self.candidates:
            url = f"{candidate['api_base']}/chat/completions"
            payload: Dict[str, Any] = {
                "model": candidate["model_name"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **self._thinking_params(candidate["model_name"]),
            }
            t0 = time.perf_counter()
            t_first: float | None = None
            token_count = 0
            try:
                resp = requests.post(
                    url,
                    headers=self._build_headers(candidate.get("api_key")),
                    json=payload,
                    stream=True,
                    timeout=120,
                )
            except requests.RequestException as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                print(f"[LLM] ✗ {candidate['model_name']} 流式连接失败 {elapsed_ms:.0f}ms | {exc}", flush=True)
                errors.append(f"{candidate['model_name']}: {exc}")
                continue
            if resp.status_code != 200:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                print(f"[LLM] ✗ {candidate['model_name']} HTTP {resp.status_code} {elapsed_ms:.0f}ms", flush=True)
                errors.append(f"{candidate['model_name']}: {resp.status_code} {resp.text}")
                continue

            for raw_line in resp.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                if isinstance(raw_line, bytes):
                    line = raw_line.decode("utf-8", errors="replace").strip()
                else:
                    line = str(raw_line).strip()
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()
                if line == "[DONE]":
                    break
                try:
                    payload_json = json.loads(line)
                except json.JSONDecodeError:
                    continue
                choices = payload_json.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    if t_first is None:
                        t_first = time.perf_counter()
                        ttft_ms = (t_first - t0) * 1000
                        print(f"[LLM] ⚡ {candidate['model_name']} 首个token {ttft_ms:.0f}ms", flush=True)
                    token_count += 1
                    yield str(content)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"[LLM] ✓ {candidate['model_name']} 流式完成 {elapsed_ms:.0f}ms | {token_count} tokens", flush=True)
            return

        raise RuntimeError(f"模型调用失败: {' | '.join(errors)}")
