from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from snapshot_consumer import (  # type: ignore
    CONTRACT_VERSION,
    MCPEnricher,
    MCPQueryPlanner,
    SkillMarkdownBuilder,
    SnapshotGapDetector,
    analyze_snapshot,
    build_command_list,
    normalize_mcp_success,
)


def _contract_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "contract.rdc", "graphics_api": "Vulkan"},
        "availability": {"status": "full", "missing_fields": [], "notes": []},
        "timings": {"available": True, "count": 1},
        "pipelines": [
            {
                "event_id": 101,
                "graphics_api": "Vulkan",
                "render_target_refs": [{"kind": "resource", "id": "rt-1"}],
                "depth_target_ref": {"kind": "resource", "id": "ds-1"},
            }
        ],
        "actions": [{"event_id": 101, "kind": "draw"}],
        "resources": {
            "textures": [
                {
                    "resource_id": "tex-1",
                    "name": "MainColor",
                    "width": 1,
                    "height": 1,
                    "depth": 1,
                    "format": "RGBA8",
                    "sample_count": 1,
                    "usage_tags": ["rt"],
                    "producer_event_refs": [],
                    "consumer_event_refs": [],
                    "availability": {"status": "full", "missing_fields": [], "notes": []},
                }
            ],
            "buffers": [],
        },
        "shaders": [
            {
                "shader_id": "s1",
                "event_id": 101,
                "stage": "pixel",
                "source_high_level": "void main(){}",
                "availability": {"status": "full", "missing_fields": [], "notes": []},
            }
        ],
        "overview": {"summary": {"draw_call_count": 1}},
    }


def _legacy_full_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "legacy.rdc", "graphics_api": "Vulkan"},
        "availability": {"status": "full", "missing_fields": [], "notes": []},
        "timings": {"available": True, "count": 1},
        "pipelines": [{"event_id": 101}],
        "actions": [{"event_id": 101, "type": "Draw", "render_targets": [{}], "depth_target": {}}],
        "resources": {"textures": [{"resource_id": "tex-1", "thumbnail": "encoded"}], "buffers": []},
        "shaders": [{"shader_id": "s1", "event_id": 101, "stage": "pixel", "source_code": "void main(){}"}],
        "overview": {"summary": {"actions": 1}},
    }


def _missing_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "missing.rdc", "graphics_api": "Vulkan"},
        "availability": {"status": "partial", "missing_fields": ["timings", "pipelines"], "notes": []},
        "timings": {},
        "pipelines": [],
        "actions": [{"event_id": 202, "kind": "draw"}, {"event_id": 201, "kind": "draw"}],
        "resources": {"textures": [{"resource_id": "tex-201"}], "buffers": []},
        "shaders": [
            {"shader_id": "s202", "event_id": 202, "stage": "vertex"},
            {"shader_id": "s201", "event_id": 201, "stage": "pixel"},
        ],
        "overview": {"summary": {"draw_call_count": 2}},
    }


def _unresolvable_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "unresolvable.rdc", "graphics_api": "Vulkan"},
        "availability": {
            "status": "partial",
            "missing_fields": ["resources.textures.thumbnail"],
            "notes": [],
        },
        "timings": {"available": True},
        "pipelines": [],
        "actions": [{"kind": "draw"}],
        "resources": {"textures": [{"name": "NoIdTexture"}], "buffers": []},
        "shaders": [{"shader_id": "x1"}],
    }


def _texture_heavy_snapshot(count: int = 80) -> Dict[str, Any]:
    textures = [{"resource_id": f"tex-{i:03d}"} for i in range(count)]
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "many_textures.rdc", "graphics_api": "Vulkan"},
        "availability": {
            "status": "partial",
            "missing_fields": ["resources.textures.thumbnail"],
            "notes": [],
        },
        "timings": {"available": True},
        "pipelines": [{"event_id": 1, "render_target_refs": [{}], "depth_target_ref": {}}],
        "actions": [{"event_id": 1, "kind": "draw"}],
        "resources": {"textures": textures, "buffers": []},
        "shaders": [],
    }


class _MockBridge:
    def __init__(self, responses: Dict[str, Any]):
        self._responses = responses
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    def call(self, method: str, params: Dict[str, Any] | None = None) -> Any:
        params = params or {}
        self.calls.append((method, params))
        if method not in self._responses:
            raise RuntimeError(f"not found: {method}")
        value = self._responses[method]
        if isinstance(value, Exception):
            raise value
        if callable(value):
            return value(params)
        return value


def test_contract_snapshot_no_gap_no_bridge_call():
    snapshot = _contract_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    assert gaps == []

    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    assert queries == []

    bridge = _MockBridge(responses={})
    result = MCPEnricher(bridge_factory=lambda: bridge).run(queries=queries, execute=True)
    assert result["status"] == "no_queries_needed"
    assert bridge.calls == []


def test_legacy_snapshot_alias_compatibility_no_gap():
    snapshot = _legacy_full_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    assert gaps == []
    assert queries == []


def test_missing_snapshot_query_order_and_dedup_stable():
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries_a = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    queries_b = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    assert queries_a == queries_b

    methods = [query["method"] for query in queries_a]
    assert methods == [
        "get_action_timings",
        "get_pipeline_state",
        "get_pipeline_state",
        "get_shader_info",
        "get_shader_info",
    ]
    commands = build_command_list(queries_a)
    assert len(commands) == len(queries_a) + 1
    assert "get_capture_status" in commands[0]
    assert all("run_query.py --method " in cmd for cmd in commands[1:])


def test_texture_query_limit_cap_applies_only_for_explicit_gap():
    snapshot = _texture_heavy_snapshot(80)
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5, texture_query_limit=12).build(snapshot, gaps)
    texture_queries = [query for query in queries if query["method"] == "get_texture_data"]
    assert len(texture_queries) == 12
    assert texture_queries[0]["params"]["resource_id"] == "tex-000"
    assert texture_queries[-1]["params"]["resource_id"] == "tex-011"


def test_unresolvable_fields_marked_non_supplementable():
    gaps = SnapshotGapDetector(max_events=5).detect(_unresolvable_snapshot())
    by_field = {gap["field_path"]: gap for gap in gaps}
    assert by_field["shaders.source_high_level"]["supplementable"] is False
    assert "unresolved_reason" in by_field["shaders.source_high_level"]["params_hint"]
    assert by_field["resources.textures.thumbnail"]["supplementable"] is False
    assert "unresolved_reason" in by_field["resources.textures.thumbnail"]["params_hint"]


def test_capture_status_loaded_false_is_success_with_hint():
    result = normalize_mcp_success({"loaded": False}, method="get_capture_status", params={})
    assert result["ok"] is True
    assert result["contract_version"] == CONTRACT_VERSION
    assert result["recovery_hint"]
    assert "capture" in result["recovery_hint"].lower()


def test_capture_not_loaded_blocks_detail_queries_with_hint():
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    bridge = _MockBridge(responses={"get_capture_status": {"loaded": False}})
    result = MCPEnricher(bridge_factory=lambda: bridge).run(queries=queries, execute=True)

    assert result["status"] == "blocked"
    assert result["blockers"][0]["code"] == "capture_not_loaded"
    assert result["health_probe"]["ok"] is True
    assert result["health_probe"]["recovery_hint"]
    assert [call[0] for call in bridge.calls] == ["get_capture_status"]


def test_capture_status_timeout_uses_bridge_diagnostic_hint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "snapshot_consumer.inspect_bridge_state",
        lambda: {
            "ipc_dir_exists": True,
            "request_present": True,
            "response_present": False,
            "lock_present": False,
        },
    )
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    bridge = _MockBridge(responses={"get_capture_status": RuntimeError("Request timed out")})
    result = MCPEnricher(bridge_factory=lambda: bridge).run(queries=queries, execute=True)

    assert result["status"] == "blocked"
    assert result["health_probe"]["error"]["code"] == "timeout"
    assert "renderdoc gui" in result["health_probe"]["recovery_hint"].lower()
    assert "replay thread" in result["health_probe"]["recovery_hint"].lower()


def test_capture_loaded_returns_envelope_per_query():
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    bridge = _MockBridge(
        responses={
            "get_capture_status": {"loaded": True},
            "get_action_timings": {"available": True, "count": 2},
            "get_pipeline_state": lambda params: {"event_id": params["event_id"]},
            "get_shader_info": lambda params: {"event_id": params["event_id"], "stage": params["stage"]},
        }
    )
    result = MCPEnricher(bridge_factory=lambda: bridge).run(
        queries=queries,
        execute=True,
        fanout={"detail_query_count": len(queries), "command_count": len(queries) + 1},
    )

    assert result["status"] == "executed"
    assert result["contract_version"] == CONTRACT_VERSION
    assert result["health_probe"]["ok"] is True
    assert result["health_probe"]["recovery_hint"]
    assert result["fanout"]["detail_query_count"] == len(queries)
    assert bridge.calls[0][0] == "get_capture_status"
    assert len(result["query_results"]) == len(queries)
    for item in result["query_results"]:
        assert item["ok"] is True
        assert item["contract_version"] == CONTRACT_VERSION
        assert "recovery_hint" in item
        assert item["source"] == "mcp"


def test_markdown_contains_required_sections_and_command_health_probe():
    snapshot = _missing_snapshot()
    analysis = analyze_snapshot(snapshot, execute=False, max_events=5, bridge_factory=lambda: _MockBridge({}))
    markdown = analysis["markdown"]
    assert "## Snapshot Facts" in markdown
    assert "Source: snapshot.v1" in markdown
    assert "## Gap Analysis" in markdown
    assert "## MCP Supplement" in markdown
    assert "## Command List" in markdown
    assert "get_capture_status" in analysis["commands"][0]

    builder = SkillMarkdownBuilder()
    rendered = builder.build(
        snapshot=snapshot,
        gaps=analysis["gaps"],
        queries=analysis["queries"],
        commands=analysis["commands"],
        enrichment=analysis["enrichment"],
    )
    assert "Snapshot Facts" in rendered
