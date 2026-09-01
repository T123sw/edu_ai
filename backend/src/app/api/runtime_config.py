from __future__ import annotations

import time
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.services.runtime_config_resolver import runtime_config_resolver
from app.services.runtime_config_store import PROVIDER_FIELDS, runtime_config_store


router = APIRouter(prefix="/api/runtime-config", tags=["runtime-config"])


class DraftRequest(BaseModel):
    scope: Literal["user", "system"] = "user"
    values: dict[str, Any] = Field(default_factory=dict)


class RevisionRequest(BaseModel):
    scope: Literal["user", "system"] = "user"
    revision_id: str = Field(min_length=1)


class ScopeRequest(BaseModel):
    scope: Literal["user", "system"] = "user"


def _owner(scope: str, current_user: dict) -> str:
    if scope == "system":
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可管理系统配置")
        return "system"
    return str(current_user.get("username") or "").strip()


def _provider(provider: str) -> str:
    if provider not in PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail="不支持的服务类型")
    return provider


class ProviderVerificationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _verify_provider(provider: str, values: dict[str, Any]) -> None:
    base_url = str(values.get("base_url") or "").rstrip("/")
    api_key = str(values.get("api_key") or "")
    if not base_url.startswith(("http://", "https://")):
        raise ProviderVerificationError(
            "invalid_endpoint", "服务地址必须以 http:// 或 https:// 开头"
        )
    timeout = max(1.0, min(120.0, float(values.get("timeout_seconds") or 15)))
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        if provider == "classroom":
            response = httpx.get(
                f"{base_url}/api/health", headers=headers, timeout=timeout
            )
        elif provider == "web_search":
            response = httpx.post(
                f"{base_url}/v1/web-search",
                headers={**headers, "Content-Type": "application/json"},
                json={"query": "教育", "count": 1},
                timeout=timeout,
            )
        elif provider == "pdf_parser":
            # MinerU and similar parsers do not expose a side-effect-free model
            # endpoint. A reachable, authenticated API root is the safest probe.
            response = httpx.get(base_url, headers=headers, timeout=timeout)
        elif provider == "tts":
            response = httpx.post(
                f"{base_url}/audio/speech",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": str(values.get("model") or ""),
                    "voice": str(values.get("voice") or "alloy"),
                    "input": "配置测试",
                    "response_format": "mp3",
                },
                timeout=timeout,
            )
        else:
            response = httpx.get(f"{base_url}/models", headers=headers, timeout=timeout)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ProviderVerificationError("timeout", f"{provider} 服务连接超时") from exc
    except httpx.ConnectError as exc:
        raise ProviderVerificationError(
            "endpoint_unreachable", f"{provider} 服务地址不可达"
        ) from exc
    except httpx.HTTPStatusError as exc:
        code = {
            401: "authentication_failed",
            403: "authentication_failed",
            404: "model_not_found",
            429: "quota_exceeded",
        }.get(exc.response.status_code, "invalid_response")
        # Deliberately omit URL headers/body so provider errors cannot leak keys.
        raise ProviderVerificationError(
            code, f"{provider} 服务连接失败（HTTP 验证未通过）"
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderVerificationError(
            "invalid_response", f"{provider} 服务返回无效响应"
        ) from exc


@router.get("")
async def list_runtime_configs(current_user: dict = Depends(get_current_user)):
    username = str(current_user.get("username") or "")
    providers = []
    for provider, fields in PROVIDER_FIELDS.items():
        user_record = runtime_config_store.list_provider(
            scope="user", owner_id=username, provider=provider
        )
        system_record = runtime_config_store.list_provider(
            scope="system", owner_id="system", provider=provider
        )
        resolved = runtime_config_resolver.resolve(provider, owner_user_id=username)
        providers.append(
            {
                "provider": provider,
                "fields": list(fields),
                "effective_source": resolved.get("_source"),
                "effective_revision_id": resolved.get("_revision_id"),
                "user": user_record,
                "system": system_record if current_user.get("role") == "admin" else None,
            }
        )
    return {"providers": providers, "can_manage_system": current_user.get("role") == "admin"}


@router.post("/{provider}/draft")
async def create_runtime_config_draft(
    provider: str,
    payload: DraftRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return runtime_config_store.create_draft(
            scope=payload.scope,
            owner_id=_owner(payload.scope, current_user),
            provider=_provider(provider),
            values=payload.values,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{provider}/verify")
async def verify_runtime_config(
    provider: str,
    payload: RevisionRequest,
    current_user: dict = Depends(get_current_user),
):
    provider = _provider(provider)
    owner_id = _owner(payload.scope, current_user)
    revision = runtime_config_store.get_revision(
        scope=payload.scope,
        owner_id=owner_id,
        provider=provider,
        revision_id=payload.revision_id,
        include_values=True,
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="配置版本不存在")
    started = time.perf_counter()
    try:
        _verify_provider(provider, revision["values"])
    except ValueError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        return runtime_config_store.mark_verification(
            scope=payload.scope,
            owner_id=owner_id,
            provider=provider,
            revision_id=payload.revision_id,
            ok=False,
            error=str(exc),
            error_code=getattr(exc, "code", "invalid_response"),
            latency_ms=latency_ms,
        )
    latency_ms = round((time.perf_counter() - started) * 1000)
    return runtime_config_store.mark_verification(
        scope=payload.scope,
        owner_id=owner_id,
        provider=provider,
        revision_id=payload.revision_id,
        ok=True,
        latency_ms=latency_ms,
    )


@router.post("/{provider}/activate")
async def activate_runtime_config(
    provider: str,
    payload: RevisionRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return runtime_config_store.activate(
            scope=payload.scope,
            owner_id=_owner(payload.scope, current_user),
            provider=_provider(provider),
            revision_id=payload.revision_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="配置版本不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{provider}/rollback")
async def rollback_runtime_config(
    provider: str,
    payload: ScopeRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return runtime_config_store.rollback(
            scope=payload.scope,
            owner_id=_owner(payload.scope, current_user),
            provider=_provider(provider),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{provider}/disable")
async def disable_runtime_config(
    provider: str,
    payload: ScopeRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return runtime_config_store.disable(
            scope=payload.scope,
            owner_id=_owner(payload.scope, current_user),
            provider=_provider(provider),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
