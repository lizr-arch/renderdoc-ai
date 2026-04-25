from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from providers import (  # type: ignore
    ProviderContext,
    SidecarLoadError,
    build_default_registry,
    load_sidecar,
)
from providers.sidecar_loader import DEFAULT_MAX_BYTES  # type: ignore
from snapshot_consumer import build_mcp_envelope  # type: ignore


SOURCE = "provider_readonly"
LOAD_SIDECAR_METHOD = "load_eap_sidecar"
ALLOWLIST_ENV = "RENDERDOC_EAP_SIDECAR_ALLOWLIST"


def parse_allowlist_env(env: Optional[Mapping[str, str]] = None) -> list[str]:
    source = env if env is not None else os.environ
    raw = source.get(ALLOWLIST_ENV, "")
    return [item for item in (part.strip() for part in raw.split(os.pathsep)) if item]


def load_eap_sidecar_envelope(
    path: str,
    *,
    allowlist_dirs: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    params = {
        "path": str(path),
        "max_bytes": int(max_bytes),
    }
    roots = [str(root) for root in allowlist_dirs]
    if not roots:
        exc = SidecarLoadError(
            "not_allowed",
            f"{ALLOWLIST_ENV} is not configured for MCP sidecar loading",
            path,
        )
        return sidecar_load_error_to_envelope(exc, method=LOAD_SIDECAR_METHOD, params=params)

    try:
        payload = load_sidecar(path, allowlist_dirs=roots, max_bytes=max_bytes)
    except SidecarLoadError as exc:
        return sidecar_load_error_to_envelope(exc, method=LOAD_SIDECAR_METHOD, params=params)

    context = ProviderContext(eap_sidecar=payload)
    data_availability = build_default_registry().data_availability(context).as_dict()
    data = {
        "sidecar": summarize_eap_sidecar(payload, path=path),
        "data_availability": data_availability,
    }
    envelope = build_mcp_envelope(
        ok=True,
        data=data,
        method=LOAD_SIDECAR_METHOD,
        params=params,
        evidence=[{"kind": "file", "path": str(Path(path).expanduser().resolve(strict=False))}],
        source=SOURCE,
    )
    envelope["source"] = SOURCE
    return envelope


def summarize_eap_sidecar(payload: Dict[str, Any], *, path: str) -> Dict[str, Any]:
    schema = payload.get("schema", {}) if isinstance(payload.get("schema"), dict) else {}
    capture = payload.get("capture", {}) if isinstance(payload.get("capture"), dict) else {}
    availability = build_default_registry().data_availability(ProviderContext(eap_sidecar=payload)).as_dict()
    capabilities = availability["providers"]["eap_sidecar"]["capabilities"]
    return {
        "path": str(Path(path).expanduser().resolve(strict=False)),
        "schema_name": schema.get("name"),
        "schema_version": schema.get("version"),
        "capture_id": capture.get("id") or availability.get("capture_id"),
        "capabilities": capabilities,
    }


def sidecar_load_error_to_envelope(
    exc: SidecarLoadError,
    *,
    method: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    mcp_code = _sidecar_code_to_mcp_code(exc.code)
    envelope = build_mcp_envelope(
        ok=False,
        data=None,
        method=method,
        params=params,
        availability={
            "status": "unavailable",
            "missing_fields": [],
            "notes": [f"sidecar_error={exc.code}"],
        },
        error={
            "code": mcp_code,
            "message": exc.message,
            "details": {
                "sidecar_code": exc.code,
                "path": exc.path,
            },
        },
        recovery_hint=_sidecar_recovery_hint(exc.code),
        source=SOURCE,
    )
    envelope["source"] = SOURCE
    return envelope


def _sidecar_code_to_mcp_code(code: str) -> str:
    if code == "not_found":
        return "not_found"
    if code in {"read_failed", "stat_failed"}:
        return "internal_error"
    return "invalid_argument"


def _sidecar_recovery_hint(code: str) -> str:
    if code == "not_allowed":
        return f"Configure {ALLOWLIST_ENV} with the directory that contains the .rmeta.json sidecar."
    if code == "invalid_extension":
        return "Use an explicit path ending in .rmeta.json."
    if code == "file_too_large":
        return "Use a smaller sidecar or raise max_bytes intentionally for this local run."
    if code == "invalid_sidecar":
        return "Provide an EngineAnnotationProtocol sidecar payload."
    if code == "not_found":
        return "Verify the sidecar path exists and retry."
    return "Fix the sidecar path or JSON payload and retry."
