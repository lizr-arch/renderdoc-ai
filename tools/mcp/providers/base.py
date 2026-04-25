from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple


DATA_AVAILABILITY_VERSION = "mcp-data-availability.v1"

PROVIDER_RENDERDOC_NATIVE = "renderdoc_native"
PROVIDER_SNAPSHOT = "snapshot"
PROVIDER_EAP_SIDECAR = "eap_sidecar"
PROVIDER_RULES = "rules"
PROVIDER_LIVE_RENDERDOC = "live_renderdoc"
PROVIDER_SCOUT_REPORT = "scout_report"
PROVIDER_ORDER = (
    PROVIDER_RENDERDOC_NATIVE,
    PROVIDER_SNAPSHOT,
    PROVIDER_EAP_SIDECAR,
    PROVIDER_RULES,
    PROVIDER_LIVE_RENDERDOC,
    PROVIDER_SCOUT_REPORT,
)


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    fields: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": self.name}
        if self.fields:
            payload["fields"] = list(self.fields)
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class DataAvailability:
    capture_id: str
    providers: Dict[str, Dict[str, Any]]
    limitations: List[str] = field(default_factory=list)
    schema_version: str = DATA_AVAILABILITY_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return stable_object(
            {
                "schema_version": self.schema_version,
                "capture_id": self.capture_id,
                "providers": self.providers,
                "limitations": self.limitations,
            }
        )


@dataclass(frozen=True)
class ProviderContext:
    capture_id: Optional[str] = None
    snapshot: Optional[Dict[str, Any]] = None
    eap_sidecar: Optional[Dict[str, Any]] = None
    rules_payload: Optional[Dict[str, Any]] = None
    live_renderdoc_status: Optional[Dict[str, Any]] = None
    bridge_state: Optional[Dict[str, Any]] = None
    scout_report: Optional[Dict[str, Any]] = None
    renderdoc_native_available: bool = True


class Provider(Protocol):
    name: str

    def availability(self, context: ProviderContext) -> Dict[str, Any]:
        ...


def capability(
    name: str,
    fields: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> ProviderCapability:
    return ProviderCapability(
        name=name,
        fields=tuple(str(field) for field in fields if str(field).strip()),
        notes=tuple(str(note) for note in notes if str(note).strip()),
    )


def provider_availability(
    *,
    available: bool,
    capabilities: Sequence[ProviderCapability] = (),
    missing: Optional[str] = None,
    notes: Sequence[str] = (),
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "available": bool(available),
        "capabilities": [item.as_dict() for item in capabilities],
    }
    if missing:
        payload["missing"] = missing
    if notes:
        payload["notes"] = list(notes)
    return stable_object(payload)


def infer_capture_id(context: ProviderContext) -> str:
    if context.capture_id:
        return str(context.capture_id)

    eap_sidecar = context.eap_sidecar if isinstance(context.eap_sidecar, dict) else {}
    snapshot = context.snapshot if isinstance(context.snapshot, dict) else {}
    capture = eap_sidecar.get("capture", {}) or {}
    meta = snapshot.get("meta", {}) or {}
    for value in (
        capture.get("id"),
        meta.get("capture_id"),
        meta.get("capture_name"),
    ):
        if value:
            return str(value)
    return "unknown"


def ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def nested_lookup(payload: Dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def extract_capture_loaded(payload: Any) -> bool:
    if isinstance(payload, dict):
        if "ok" in payload and isinstance(payload.get("data"), dict):
            return bool((payload.get("data") or {}).get("loaded", False))
        return bool(payload.get("loaded", False))
    return False


def stable_object(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))
