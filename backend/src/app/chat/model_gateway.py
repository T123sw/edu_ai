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
                print(f"[LLM] fail {candidate['model_name']} 同步调用失败 {elapsed_ms:.0f}ms | {exc}", flush=True)
                errors.append(f"{candidate['model_name']}: {exc}")
                continue
            if resp.status_code != 200:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                print(f"[LLM] fail {candidate['model_name']} HTTP {resp.status_code} {elapsed_ms:.0f}ms", flush=True)
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
            print(f"[LLM] ok {candidate['model_name']} 同步调用 {elapsed_ms:.0f}ms | {len(content)} 字符", flush=True)
            return content

        raise RuntimeError(f"模型调用失败: {' | '.join(errors)}")

    def stream_chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> Iterable[Dict[str, Any]]:
        """Streaming call with function calling support.

        Yields:
          {"type": "text_delta", "content": str}   — forwarded immediately for low TTFT
          {"type": "tool_calls", "calls": list}     — after finish_reason=tool_calls
          {"type": "done"}
          {"type": "unsupported"}                   — model doesn't support tools
          {"type": "error", "message": str}
        """
        errors: List[str] = []
        for candidate in self.candidates:
            url = f"{candidate['api_base']}/chat/completions"
            req_payload: Dict[str, Any] = {
                "model": candidate["model_name"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **self._thinking_params(candidate["model_name"]),
            }
            # Only include tools/tool_choice when the caller actually provides tools.
            # Some providers (e.g. Qwen) reject empty tool arrays.
            if tools:
                req_payload["tools"] = tools
                req_payload["tool_choice"] = tool_choice
            t0 = time.perf_counter()
            t_first: float | None = None
            try:
                resp = requests.post(
                    url,
                    headers=self._build_headers(candidate.get("api_key")),
                    json=req_payload,
                    stream=True,
                    timeout=120,
                )
            except requests.RequestException as exc:
                errors.append(f"{candidate['model_name']}: {exc}")
                continue
            if resp.status_code != 200:
                body_preview = resp.text[:400] if resp.text else ""
                print(f"[LLM] 工具调用失败 | {candidate['model_name']} HTTP {resp.status_code} | {body_preview}", flush=True)
                errors.append(f"{candidate['model_name']}: HTTP {resp.status_code}")
                continue

            accumulated_tool_calls: Dict[int, Dict[str, Any]] = {}

            for raw_line in resp.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                line = (raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line).strip()
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                finish_reason = choice.get("finish_reason")

                content = delta.get("content")
                if content:
                    if t_first is None:
                        t_first = time.perf_counter()
                        print(f"[AGENT] ttft {(t_first - t0)*1000:.0f}ms", flush=True)
                    yield {"type": "text_delta", "content": str(content)}

                for tc in (delta.get("tool_calls") or []):
                    idx = tc.get("index", 0)
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        accumulated_tool_calls[idx]["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        accumulated_tool_calls[idx]["function"]["arguments"] += fn["arguments"]
                    if tc.get("id"):
                        accumulated_tool_calls[idx]["id"] = tc["id"]

                if finish_reason == "tool_calls":
                    calls = []
                    for idx in sorted(accumulated_tool_calls.keys()):
                        tc = accumulated_tool_calls[idx]
                        try:
                            args = json.loads(tc["function"]["arguments"] or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        calls.append({
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "args": args,
                        })
                    print(f"[AGENT] tool_calls: {[c['name'] for c in calls]} {(time.perf_counter()-t0)*1000:.0f}ms", flush=True)
                    yield {"type": "tool_calls", "calls": calls}
                    yield {"type": "done"}
                    return

                if finish_reason == "stop":
                    yield {"type": "done"}
                    return

            if accumulated_tool_calls:
                calls = []
                for idx in sorted(accumulated_tool_calls.keys()):
                    tc = accumulated_tool_calls[idx]
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    calls.append({"id": tc["id"], "name": tc["function"]["name"], "args": args})
                yield {"type": "tool_calls", "calls": calls}
            yield {"type": "done"}
            return

        yield {"type": "error", "message": f"所有模型失败: {' | '.join(errors)}"}

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
                print(f"[LLM] fail {candidate['model_name']} 流式连接失败 {elapsed_ms:.0f}ms | {exc}", flush=True)
                errors.append(f"{candidate['model_name']}: {exc}")
                continue
            if resp.status_code != 200:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                print(f"[LLM] fail {candidate['model_name']} HTTP {resp.status_code} {elapsed_ms:.0f}ms", flush=True)
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
                        print(f"[LLM] ttft {candidate['model_name']} {ttft_ms:.0f}ms", flush=True)
                    token_count += 1
                    yield str(content)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            print(f"[LLM] ok {candidate['model_name']} 流式完成 {elapsed_ms:.0f}ms | {token_count} tokens", flush=True)
            return

        raise RuntimeError(f"模型调用失败: {' | '.join(errors)}")
