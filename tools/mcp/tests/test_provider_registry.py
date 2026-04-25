from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers import (  # type: ignore
    PROVIDER_ORDER,
    ProviderContext,
    build_default_registry,
)
from snapshot_consumer import build_data_availability, get_data_availability  # type: ignore


def _snapshot(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": "snapshot.v1",
        "meta": {"capture_id": "cap:snapshot", "capture_name": "snapshot.rdc"},
        "preflight": {"status": "ok"},
        "availability": {"status": "full", "missing_fields": [], "notes": []},
        "actions": [{"event_id": 1, "kind": "draw"}],
        "resources": {"textures": [{"resource_id": "tex:1"}], "buffers": []},
        "timings": {"available": True, "count": 1},
        "pipelines": [{"event_id": 1}],
        "shaders": [{"shader_id": "shader:1"}],
        "findings": [],
        "recommendations": [],
        "evidence_index": {"event:1": {"anchor": "event-1"}},
    }
    payload.update(extra)
    return payload


def _sidecar(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": {"name": "EngineAnnotationProtocol", "version": 1},
        "capture": {"id": "cap:eap"},
        "render_graph": {"nodes": [{"id": "pass:main"}]},
        "commands": [{"id": "cmd:1"}],
        "resources": [{"id": "res:1"}],
        "diagnostics": {"missing_fields": []},
    }
    payload.update(extra)
    return payload


def _availability(context: ProviderContext) -> Dict[str, Any]:
    return build_default_registry().data_availability(context).as_dict()


def test_no_payloads_keeps_native_available_and_lists_missing_providers():
    payload = _availability(ProviderContext(capture_id="cap:none"))

    assert payload["schema_version"] == "mcp-data-availability.v1"
    assert payload["capture_id"] == "cap:none"
    assert list(payload["providers"]) == list(PROVIDER_ORDER)
    assert payload["providers"]["renderdoc_native"]["available"] is True
    assert payload["providers"]["snapshot"]["missing"] == "snapshot.v1 payload not provided"
    assert payload["providers"]["eap_sidecar"]["missing"] == "capture.rmeta.json not found"
    assert payload["providers"]["rules"]["missing"] == (
        "No rules payload, EAP rule results, or snapshot findings provided"
    )
    assert payload["providers"]["live_renderdoc"]["missing"] == "live RenderDoc bridge not probed"
    assert payload["providers"]["scout_report"]["missing"] == "scout report not provided"
    assert payload["limitations"] == [
        "snapshot: snapshot.v1 payload not provided",
        "eap_sidecar: capture.rmeta.json not found",
        "rules: No rules payload, EAP rule results, or snapshot findings provided",
        "live_renderdoc: live RenderDoc bridge not probed",
        "scout_report: scout report not provided",
    ]


def test_snapshot_only_marks_snapshot_available_and_sidecar_missing():
    payload = _availability(ProviderContext(snapshot=_snapshot()))

    assert payload["capture_id"] == "cap:snapshot"
    assert payload["providers"]["snapshot"]["available"] is True
    assert payload["providers"]["eap_sidecar"]["available"] is False
    assert payload["providers"]["eap_sidecar"]["missing"] == "capture.rmeta.json not found"
    capability_names = {item["name"] for item in payload["providers"]["snapshot"]["capabilities"]}
    assert {"snapshot_meta", "snapshot_actions", "snapshot_resources", "snapshot_timings"} <= capability_names


def test_eap_sidecar_only_reports_present_sidecar_sections():
    payload = _availability(ProviderContext(eap_sidecar=_sidecar(shaders=[{"id": "shader:1"}])))

    assert payload["capture_id"] == "cap:eap"
    assert payload["providers"]["snapshot"]["available"] is False
    assert payload["providers"]["eap_sidecar"]["available"] is True
    capability_names = {item["name"] for item in payload["providers"]["eap_sidecar"]["capabilities"]}
    assert {"eap_schema", "render_graph", "commands", "resources", "shaders", "diagnostics"} <= capability_names


def test_sidecar_rules_make_rules_provider_available():
    payload = _availability(ProviderContext(eap_sidecar=_sidecar(rules={"results": [{"id": "rule:1"}]})))

    assert payload["providers"]["rules"]["available"] is True
    assert payload["providers"]["rules"]["capabilities"] == [
        {"name": "eap_sidecar_rule_results", "fields": ["rules.results"]}
    ]


def test_external_rules_payload_makes_rules_provider_available():
    payload = _availability(ProviderContext(rules_payload={"results": [{"id": "external:rule"}]}))

    assert payload["providers"]["rules"]["available"] is True
    assert payload["providers"]["rules"]["capabilities"] == [
        {"name": "external_rule_results", "fields": ["rules_payload"]}
    ]


def test_snapshot_findings_make_rules_provider_available():
    snapshot = _snapshot(findings=[{"id": "finding:1"}])
    payload = _availability(ProviderContext(snapshot=snapshot))

    assert payload["providers"]["rules"]["available"] is True
    assert payload["providers"]["rules"]["capabilities"] == [
        {"name": "snapshot_findings", "fields": ["findings", "recommendations"]}
    ]


def test_live_status_loaded_false_marks_live_renderdoc_unavailable():
    payload = _availability(ProviderContext(live_renderdoc_status={"loaded": False}))

    assert payload["providers"]["live_renderdoc"]["available"] is False
    assert payload["providers"]["live_renderdoc"]["missing"] == "live RenderDoc capture is not loaded"
    assert "live_renderdoc: live RenderDoc capture is not loaded" in payload["limitations"]


def test_live_status_loaded_true_marks_live_renderdoc_available():
    payload = _availability(ProviderContext(live_renderdoc_status={"ok": True, "data": {"loaded": True}}))

    assert payload["providers"]["live_renderdoc"]["available"] is True
    assert payload["providers"]["live_renderdoc"]["capabilities"] == [
        {
            "name": "live_capture_queries",
            "fields": ["capture_status", "frame_summary", "pipeline_state", "texture_data"],
        }
    ]


def test_provider_output_order_is_stable():
    payload = _availability(ProviderContext())

    assert list(payload["providers"].keys()) == list(PROVIDER_ORDER)


def test_snapshot_consumer_wrapper_matches_default_registry():
    context = ProviderContext(
        capture_id="cap:wrapper",
        snapshot=_snapshot(),
        eap_sidecar=_sidecar(rules={"results": [{"id": "rule:1"}]}),
        live_renderdoc_status={"loaded": True},
        scout_report={"implementation_candidates": []},
    )

    registry_payload = _availability(context)
    wrapper_payload = get_data_availability(
        capture_id=context.capture_id,
        snapshot=context.snapshot,
        eap_sidecar=context.eap_sidecar,
        live_renderdoc_status=context.live_renderdoc_status,
        scout_report=context.scout_report,
    )
    data_object_payload = build_data_availability(
        capture_id=context.capture_id,
        snapshot=context.snapshot,
        eap_sidecar=context.eap_sidecar,
        live_renderdoc_status=context.live_renderdoc_status,
        scout_report=context.scout_report,
    ).as_dict()

    assert wrapper_payload == registry_payload
    assert data_object_payload == registry_payload
