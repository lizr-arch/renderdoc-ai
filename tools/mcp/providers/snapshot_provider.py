from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import (
    PROVIDER_SNAPSHOT,
    ProviderCapability,
    ProviderContext,
    capability,
    provider_availability,
)


class SnapshotProvider:
    name = PROVIDER_SNAPSHOT

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        snapshot = context.snapshot
        missing = _snapshot_missing_reason(snapshot)
        if missing:
            return provider_availability(available=False, missing=missing)
        return provider_availability(
            available=True,
            capabilities=_snapshot_capabilities(snapshot or {}),
        )


def _snapshot_missing_reason(snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(snapshot, dict) or not snapshot:
        return "snapshot.v1 payload not provided"
    if snapshot.get("schema_version") != "snapshot.v1":
        return "payload is not snapshot.v1"
    return None


def _snapshot_capabilities(snapshot: Dict[str, Any]) -> List[ProviderCapability]:
    capabilities = [
        capability("snapshot_meta", ["meta", "preflight", "availability"]),
    ]
    section_fields = [
        ("snapshot_actions", "actions"),
        ("snapshot_resources", "resources"),
        ("snapshot_timings", "timings"),
        ("snapshot_pipelines", "pipelines"),
        ("snapshot_shaders", "shaders"),
        ("snapshot_findings", "findings"),
        ("snapshot_recommendations", "recommendations"),
        ("snapshot_evidence_index", "evidence_index"),
    ]
    for name, field_path in section_fields:
        value = snapshot.get(field_path)
        if isinstance(value, dict) and value:
            capabilities.append(capability(name, [field_path]))
        elif isinstance(value, list) and value:
            capabilities.append(capability(name, [field_path]))
    return capabilities
