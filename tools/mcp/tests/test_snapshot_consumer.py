from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List


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
)


def _full_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "full.rdc", "graphics_api": "Vulkan"},
        "availability": {"status": "full", "missing_fields": [], "notes": []},
        "timings": {"available": True, "count": 1},
        "pipelines": [{"event_id": 101}],
        "actions": [{"event_id": 101, "type": "Draw", "render_targets": [{}], "depth_target": {}}],
        "resources": {"textures": [{"resource_id": "tex-1", "thumbnail": "encoded"}], "buffers": []},
        "shaders": [{"shader_id": "s1", "event_id": 101, "stage": "pixel", "source_code": "void main(){}"}],
        "overview": {"summary": {"actions": 1, "textures": 1, "shaders": 1}},
    }


def _missing_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "missing.rdc", "graphics_api": "Vulkan"},
        "availability": {"status": "partial", "missing_fields": ["timings", "pipelines"], "notes": []},
        "timings": {},
        "pipelines": [],
        "actions": [{"event_id": 202, "type": "Draw"}, {"event_id": 201, "type": "Draw"}],
        "resources": {"textures": [{"resource_id": "tex-201", "thumbnail": ""}], "buffers": []},
        "shaders": [
            {"shader_id": "s202", "event_id": 202, "stage": "vertex", "source_code": ""},
            {"shader_id": "s201", "event_id": 201, "stage": "pixel", "source_code": ""},
        ],
        "overview": {"summary": {"actions": 2, "textures": 1, "shaders": 2}},
    }


def _unresolvable_snapshot() -> Dict[str, Any]:
    return {
        "schema_version": "snapshot.v1",
        "meta": {"capture_name": "unresolvable.rdc", "graphics_api": "Vulkan"},
        "availability": {"status": "partial", "missing_fields": [], "notes": []},
        "timings": {"available": True},
        "pipelines": [],
        "actions": [{"type": "Draw"}],
        "resources": {"textures": [{"thumbnail": ""}], "buffers": []},
        "shaders": [{"shader_id": "x1", "source_code": ""}],
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


def test_full_snapshot_no_gap_no_bridge_call():
    snapshot = _full_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    assert gaps == []

    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    assert queries == []

    bridge = _MockBridge(responses={})
    result = MCPEnricher(bridge_factory=lambda: bridge).run(queries=queries, execute=True)
    assert result["status"] == "no_queries_needed"
    assert bridge.calls == []


def test_missing_snapshot_query_order_and_dedup_stable():
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries_a = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    queries_b = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    assert queries_a == queries_b

    methods = [q["method"] for q in queries_a]
    assert methods == [
        "get_action_timings",
        "get_pipeline_state",
        "get_pipeline_state",
        "get_shader_info",
        "get_shader_info",
        "get_texture_data",
    ]
    assert queries_a[1]["params"]["event_id"] == 201
    assert queries_a[2]["params"]["event_id"] == 202

    commands = build_command_list(queries_a)
    assert len(commands) == len(queries_a)
    assert all("run_query.py --method " in cmd for cmd in commands)


def test_unresolvable_fields_marked_non_supplementable():
    gaps = SnapshotGapDetector(max_events=5).detect(_unresolvable_snapshot())
    by_field = {g["field_path"]: g for g in gaps}
    assert by_field["shaders.source_code"]["supplementable"] is False
    assert "unresolved_reason" in by_field["shaders.source_code"]["params_hint"]
    assert by_field["resources.textures.thumbnail"]["supplementable"] is False
    assert "unresolved_reason" in by_field["resources.textures.thumbnail"]["params_hint"]


def test_capture_not_loaded_blocks_detail_queries_with_hint():
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    bridge = _MockBridge(responses={"get_capture_status": {"loaded": False}})
    result = MCPEnricher(bridge_factory=lambda: bridge).run(queries=queries, execute=True)

    assert result["status"] == "blocked"
    assert result["blockers"][0]["code"] == "capture_not_loaded"
    assert result["recovery_hint"]
    assert [x[0] for x in bridge.calls] == ["get_capture_status"]


def test_capture_loaded_returns_envelope_per_query():
    snapshot = _missing_snapshot()
    gaps = SnapshotGapDetector(max_events=5).detect(snapshot)
    queries = MCPQueryPlanner(max_events=5).build(snapshot, gaps)
    bridge = _MockBridge(
        responses={
            "get_capture_status": {"loaded": True},
            "get_action_timings": {"available": True, "count": 2},
            "get_pipeline_state": lambda p: {"event_id": p["event_id"]},
            "get_shader_info": lambda p: {"event_id": p["event_id"], "stage": p["stage"]},
            "get_texture_data": lambda p: {"resource_id": p["resource_id"]},
        }
    )
    result = MCPEnricher(bridge_factory=lambda: bridge).run(queries=queries, execute=True)

    assert result["status"] == "executed"
    assert result["contract_version"] == CONTRACT_VERSION
    assert bridge.calls[0][0] == "get_capture_status"
    assert len(result["query_results"]) == len(queries)
    for item in result["query_results"]:
        assert item["ok"] is True
        assert item["contract_version"] == CONTRACT_VERSION
        assert "data" in item
        assert "availability" in item
        assert "evidence" in item
        assert "warnings" in item
        assert "recovery_hint" in item
        assert "method" in item and "params" in item
        assert item["source"] == "mcp"


def test_markdown_contains_required_sections_and_sources():
    snapshot = _missing_snapshot()
    analysis = analyze_snapshot(snapshot, execute=False, max_events=5, bridge_factory=lambda: _MockBridge({}))
    markdown = analysis["markdown"]
    assert "## Snapshot Facts" in markdown
    assert "Source: snapshot.v1" in markdown
    assert "## Gap Analysis" in markdown
    assert "## MCP Supplement" in markdown
    assert "Source: MCP query" in markdown
    assert "## Command List" in markdown

    builder = SkillMarkdownBuilder()
    rendered = builder.build(
        snapshot=snapshot,
        gaps=analysis["gaps"],
        queries=analysis["queries"],
        commands=analysis["commands"],
        enrichment=analysis["enrichment"],
    )
    assert "Snapshot Facts" in rendered

