from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from providers import (  # type: ignore
    ProviderContext,
    SidecarLoadError,
    build_default_registry,
    load_sidecar,
)
from providers.sidecar_loader import DEFAULT_MAX_BYTES  # type: ignore
from snapshot_consumer import build_mcp_envelope  # type: ignore

from .eap_sidecar_consumption import (
    DEFAULT_SEARCH_LIMIT,
    count_eap_sections,
    normalize_limit,
    rule_results_data,
    search_commands_data,
)


SOURCE = "provider_readonly"
LOAD_SIDECAR_METHOD = "load_eap_sidecar"
SUMMARIZE_SIDECAR_METHOD = "summarize_eap_sidecar"
SEARCH_COMMANDS_METHOD = "search_eap_commands"
GET_RULE_RESULTS_METHOD = "get_eap_rule_results"
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


def summarize_eap_sidecar_envelope(
    path: str,
    *,
    allowlist_dirs: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    params = {
        "path": str(path),
        "max_bytes": int(max_bytes),
    }
    payload, error = _load_sidecar_for_method(
        path,
        allowlist_dirs=allowlist_dirs,
        max_bytes=max_bytes,
        method=SUMMARIZE_SIDECAR_METHOD,
        params=params,
    )
    if error is not None:
        return error

    data_availability = build_default_registry().data_availability(
        ProviderContext(eap_sidecar=payload)
    ).as_dict()
    data = {
        "summary": summarize_eap_sidecar(payload, path=path),
        "counts": count_eap_sections(payload),
        "data_availability": data_availability,
        "validation_scope": "synthetic_fixture_or_explicit_sidecar_only",
    }
    return _success_envelope(
        data=data,
        method=SUMMARIZE_SIDECAR_METHOD,
        params=params,
        path=path,
    )


def search_eap_commands_envelope(
    path: str,
    *,
    query: str = "",
    pass_id: str = "",
    resource_id: str = "",
    material_id: str = "",
    shader_id: str = "",
    pipeline_id: str = "",
    limit: int = DEFAULT_SEARCH_LIMIT,
    allowlist_dirs: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    normalized_limit = normalize_limit(limit)
    params = {
        "path": str(path),
        "query": str(query),
        "pass_id": str(pass_id),
        "resource_id": str(resource_id),
        "material_id": str(material_id),
        "shader_id": str(shader_id),
        "pipeline_id": str(pipeline_id),
        "limit": normalized_limit,
        "max_bytes": int(max_bytes),
    }
    payload, error = _load_sidecar_for_method(
        path,
        allowlist_dirs=allowlist_dirs,
        max_bytes=max_bytes,
        method=SEARCH_COMMANDS_METHOD,
        params=params,
    )
    if error is not None:
        return error

    filters = {
        "query": str(query).strip(),
        "pass_id": str(pass_id).strip(),
        "resource_id": str(resource_id).strip(),
        "material_id": str(material_id).strip(),
        "shader_id": str(shader_id).strip(),
        "pipeline_id": str(pipeline_id).strip(),
    }
    data = search_commands_data(payload, filters=filters, limit=normalized_limit)
    return _success_envelope(
        data=data,
        method=SEARCH_COMMANDS_METHOD,
        params=params,
        path=path,
    )


def get_eap_rule_results_envelope(
    path: str,
    *,
    severity: str = "",
    limit: int = DEFAULT_SEARCH_LIMIT,
    allowlist_dirs: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    normalized_limit = normalize_limit(limit)
    params = {
        "path": str(path),
        "severity": str(severity),
        "limit": normalized_limit,
        "max_bytes": int(max_bytes),
    }
    payload, error = _load_sidecar_for_method(
        path,
        allowlist_dirs=allowlist_dirs,
        max_bytes=max_bytes,
        method=GET_RULE_RESULTS_METHOD,
        params=params,
    )
    if error is not None:
        return error

    data = rule_results_data(payload, severity=severity, limit=normalized_limit)
    return _success_envelope(
        data=data,
        method=GET_RULE_RESULTS_METHOD,
        params=params,
        path=path,
    )


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


def _load_sidecar_for_method(
    path: str,
    *,
    allowlist_dirs: Iterable[str],
    max_bytes: int,
    method: str,
    params: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    roots = [str(root) for root in allowlist_dirs]
    if not roots:
        exc = SidecarLoadError(
            "not_allowed",
            f"{ALLOWLIST_ENV} is not configured for MCP sidecar loading",
            path,
        )
        return None, sidecar_load_error_to_envelope(exc, method=method, params=params)

    try:
        return load_sidecar(path, allowlist_dirs=roots, max_bytes=max_bytes), None
    except SidecarLoadError as exc:
        return None, sidecar_load_error_to_envelope(exc, method=method, params=params)


def _success_envelope(
    *,
    data: Dict[str, Any],
    method: str,
    params: Dict[str, Any],
    path: str,
) -> Dict[str, Any]:
    envelope = build_mcp_envelope(
        ok=True,
        data=data,
        method=method,
        params=params,
        evidence=[{"kind": "file", "path": str(Path(path).expanduser().resolve(strict=False))}],
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
