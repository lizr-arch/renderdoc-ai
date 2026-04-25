from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import (
    PROVIDER_EAP_SIDECAR,
    ProviderCapability,
    ProviderContext,
    capability,
    nested_lookup,
    provider_availability,
)


class EAPSidecarProvider:
    name = PROVIDER_EAP_SIDECAR

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        eap_sidecar = context.eap_sidecar
        missing = _eap_sidecar_missing_reason(eap_sidecar)
        if missing:
            return provider_availability(available=False, missing=missing)
        return provider_availability(
            available=True,
            capabilities=_eap_sidecar_capabilities(eap_sidecar or {}),
        )


def _eap_sidecar_missing_reason(eap_sidecar: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(eap_sidecar, dict) or not eap_sidecar:
        return "capture.rmeta.json not found"
    if not looks_like_eap_sidecar(eap_sidecar):
        return "payload is not an EAP sidecar"
    return None


def looks_like_eap_sidecar(payload: Dict[str, Any]) -> bool:
    schema = payload.get("schema", {}) or {}
    if isinstance(schema, dict) and str(schema.get("name", "")).lower() == "engineannotationprotocol":
        return True
    expected_keys = {
        "capture",
        "render_graph",
        "commands",
        "resources",
        "materials",
        "shaders",
        "pipelines",
        "rules",
        "diagnostics",
    }
    return any(key in payload for key in expected_keys)


_looks_like_eap_sidecar = looks_like_eap_sidecar


def _eap_sidecar_capabilities(payload: Dict[str, Any]) -> List[ProviderCapability]:
    capabilities = [capability("eap_schema", ["schema", "capture"])]
    field_map = [
        ("render_graph", "render_graph.nodes"),
        ("commands", "commands"),
        ("resources", "resources"),
        ("assets", "assets"),
        ("materials", "materials"),
        ("shaders", "shaders"),
        ("pipelines", "pipelines"),
        ("rules", "rules.results"),
        ("diagnostics", "diagnostics"),
        ("security", "security"),
    ]
    for name, field_path in field_map:
        value = nested_lookup(payload, field_path)
        if isinstance(value, dict) and value:
            capabilities.append(capability(name, [field_path]))
        elif isinstance(value, list) and value:
            capabilities.append(capability(name, [field_path]))
    return capabilities
