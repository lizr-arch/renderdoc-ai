"""
RenderDoc data richness baseline for A-route output.

This module defines the official field baselines (ActionDescription / TextureDescription)
and provides coverage helpers that never approximate missing values. If a field cannot
be derived, it must be reported as missing with a reason.
"""

from typing import Dict, Any, List, Optional

MISSING_REASON_REPLAY = "Not in XML / requires replay"


# Standard fields from RenderDoc ActionDescription (names match official API).
# Mapping to A-route keys is explicit; any non-1:1 mapping is marked as partial.
ACTION_FIELD_MAP: Dict[str, Dict[str, Any]] = {
    "eventId": {"keys": ["eventId", "eid"]},
    "actionId": {"keys": ["actionId"]},
    "customName": {
        "keys": ["customName", "name"],
        "note": "Mapped from event name; customName not explicit in XML",
    },
    "flags": {"keys": ["flags"]},
    "markerColor": {"keys": ["markerColor"]},
    "numIndices": {
        "keys": ["numIndices", "index_count"],
        "note": "Mapped from index_count; may differ from ActionDescription numIndices",
    },
    "numInstances": {
        "keys": ["numInstances", "instance_count"],
        "note": "Mapped from instance_count; may differ from ActionDescription numInstances",
    },
    "baseVertex": {"keys": ["baseVertex"]},
    "indexOffset": {"keys": ["indexOffset"]},
    "vertexOffset": {"keys": ["vertexOffset"]},
    "instanceOffset": {"keys": ["instanceOffset"]},
    "drawIndex": {"keys": ["drawIndex"]},
    "dispatchDimension": {"keys": ["dispatchDimension", "dispatch_dimension"]},
    "dispatchThreadsDimension": {
        "keys": ["dispatchThreadsDimension", "dispatch_threads_dimension"],
    },
    "dispatchBase": {"keys": ["dispatchBase", "dispatch_base"]},
    "copySource": {"keys": ["copySource"]},
    "copyDestination": {"keys": ["copyDestination"]},
    "outputs": {
        "keys": ["outputs", "render_targets"],
        "note": "Mapped from render_targets; ActionDescription outputs is a ResourceId tuple",
    },
    "depthOut": {
        "keys": ["depthOut", "depth_target"],
        "note": "Mapped from depth_target; ActionDescription depthOut is a ResourceId",
    },
    "events": {"keys": ["events"]},
    "children": {"keys": ["children"]},
}


# Standard fields from RenderDoc TextureDescription.
TEXTURE_FIELD_MAP: Dict[str, Dict[str, Any]] = {
    "format": {"keys": ["format"]},
    "dimension": {"keys": ["dimension"]},
    "type": {"keys": ["type"]},
    "width": {"keys": ["width"]},
    "height": {"keys": ["height"]},
    "depth": {"keys": ["depth"]},
    "resourceId": {
        "keys": ["resourceId", "id"],
        "note": "Mapped from id; may not equal RenderDoc ResourceId",
    },
    "cubemap": {"keys": ["cubemap"]},
    "mips": {"keys": ["mips", "mipLevels"]},
    "arraysize": {
        "keys": ["arraysize", "arrayLayers"],
        "note": "Mapped from arrayLayers; RenderDoc uses arraysize",
    },
    "creationFlags": {"keys": ["creationFlags"]},
    "msQual": {"keys": ["msQual"]},
    "msSamp": {"keys": ["msSamp"]},
    "byteSize": {"keys": ["byteSize"]},
}


def _first_key_present(keys: List[str], actual: Dict[str, Any]) -> Optional[str]:
    for key in keys:
        if key in actual:
            return key
    return None


def compute_field_coverage(
    field_map: Dict[str, Dict[str, Any]],
    actual: Dict[str, Any],
    missing_reason: str = MISSING_REASON_REPLAY,
) -> Dict[str, Any]:
    present: List[str] = []
    partial: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for field, spec in field_map.items():
        keys = spec.get("keys", [])
        note = spec.get("note")
        found_key = _first_key_present(keys, actual)
        if found_key:
            if note:
                partial.append(
                    {
                        "field": field,
                        "mapped_from": found_key,
                        "reason": note,
                    }
                )
            else:
                present.append(field)
        else:
            missing.append({"field": field, "reason": missing_reason})

    return {
        "present": present,
        "partial": partial,
        "missing": missing,
        "standard": "RenderDoc",
    }
