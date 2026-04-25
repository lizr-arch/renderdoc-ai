from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers import ProviderContext, build_default_registry  # type: ignore


def _snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_id": "cap:snapshot"},
        "actions": [{"event_id": 1, "kind": "draw"}],
        "resources": {"textures": [{"resource_id": "tex:1"}], "buffers": []},
    }


def _sidecar() -> Dict[str, Any]:
    return {
        "schema": {"name": "EngineAnnotationProtocol", "version": 1},
        "capture": {"id": "cap:eap"},
        "commands": [{"id": "cmd:1"}],
        "resources": [{"id": "res:1"}],
    }


def _route(method: str, context: ProviderContext, preferred_provider: str | None = None) -> Dict[str, Any]:
    return build_default_registry().route(
        method,
        preferred_provider=preferred_provider,
        context=context,
    )


def test_capture_status_routes_to_live_when_loaded():
    route = _route(
        "get_capture_status",
        ProviderContext(live_renderdoc_status={"ok": True, "data": {"loaded": True}}),
    )

    assert route["ok"] is True
    assert route["contract_version"] == "mcp-query.v1"
    assert route["data"]["provider"] == "live_renderdoc"
    assert route["data"]["method"] == "get_capture_status"


def test_capture_status_falls_back_to_native_when_live_unavailable():
    route = _route("get_capture_status", ProviderContext())

    assert route["ok"] is True
    assert route["data"]["provider"] == "renderdoc_native"


def test_snapshot_query_routes_without_eap_sidecar():
    route = _route("get_frame_summary", ProviderContext(snapshot=_snapshot()))

    assert route["ok"] is True
    assert route["data"]["provider"] == "snapshot"


def test_pipeline_state_prefers_live_then_snapshot():
    live_route = _route(
        "get_pipeline_state",
        ProviderContext(
            snapshot=_snapshot(),
            live_renderdoc_status={"ok": True, "data": {"loaded": True}},
        ),
    )
    snapshot_route = _route("get_pipeline_state", ProviderContext(snapshot=_snapshot()))

    assert live_route["data"]["provider"] == "live_renderdoc"
    assert snapshot_route["data"]["provider"] == "snapshot"


def test_eap_only_query_without_sidecar_returns_data_unavailable():
    route = _route("get_eap_command", ProviderContext())

    assert route["ok"] is False
    assert route["error"]["code"] == "data_unavailable"
    assert route["availability"]["status"] == "unavailable"
    assert "eap_sidecar" in route["availability"]["notes"][0]


def test_eap_only_query_with_sidecar_routes_to_eap_provider():
    route = _route("get_eap_command", ProviderContext(eap_sidecar=_sidecar()))

    assert route["ok"] is True
    assert route["data"]["provider"] == "eap_sidecar"


def test_unknown_method_returns_unsupported_api():
    route = _route("get_magic_answer", ProviderContext(snapshot=_snapshot(), eap_sidecar=_sidecar()))

    assert route["ok"] is False
    assert route["error"]["code"] == "unsupported_api"
    assert route["recovery_hint"] == "Choose a supported MCP provider method."


def test_preferred_provider_must_handle_method():
    route = _route(
        "get_rule_results",
        ProviderContext(rules_payload={"results": [{"id": "rule:1"}]}),
        preferred_provider="snapshot",
    )

    assert route["ok"] is False
    assert route["error"]["code"] == "unsupported_api"
    assert "snapshot" in route["error"]["message"]


def test_preferred_provider_must_be_available():
    route = _route("get_frame_summary", ProviderContext(), preferred_provider="snapshot")

    assert route["ok"] is False
    assert route["error"]["code"] == "data_unavailable"
    assert "snapshot.v1 payload not provided" in route["availability"]["notes"][0]
