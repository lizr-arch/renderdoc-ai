from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


CONTRACT_VERSION = "mcp-query.v1"

REASON_LAYER_SCHEMA_DECLARED = "schema_declared_gap"
REASON_LAYER_VALUE_MISSING = "value_missing"
REASON_LAYER_API_UNSUPPORTED = "api_not_supported"

_UNSUPPORTED_HINT_KEYWORDS = ("unsupported", "not supported", "not expose", "unavailable")
_VALID_SHADER_STAGES = {"vertex", "hull", "domain", "geometry", "pixel", "compute"}
_PIPELINE_GAP_FIELDS = {
    "pipelines",
    "pipelines.render_target_refs",
    "pipelines.depth_target_ref",
    "actions[].render_targets",
    "actions[].depth_target",
}
_SHADER_GAP_FIELDS = {"shaders.source_high_level", "shaders.source_asm", "shaders.source_code"}
_TEXTURE_THUMBNAIL_FIELD = "resources.textures.thumbnail"
_GAP_PRIORITY = {
    "timings": 0,
    "pipelines": 1,
    "pipelines.render_target_refs": 2,
    "pipelines.depth_target_ref": 3,
    "actions[].render_targets": 4,
    "actions[].depth_target": 5,
    "shaders.source_high_level": 6,
    "shaders.source_asm": 7,
    "shaders.source_code": 8,
    _TEXTURE_THUMBNAIL_FIELD: 9,
}
_QUERY_PRIORITY = {
    "get_action_timings": 0,
    "get_pipeline_state": 1,
    "get_shader_info": 2,
    "get_texture_data": 3,
}


@dataclass(frozen=True)
class QuerySpec:
    method: str
    params: Dict[str, Any]
    reason: str
    field_path: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "params": self.params,
            "reason": self.reason,
            "field_path": self.field_path,
        }


class SnapshotGapDetector:
    def __init__(self, max_events: int = 5, implicit_texture_fetch: bool = False):
        self._max_events = max(1, int(max_events))
        self._implicit_texture_fetch = bool(implicit_texture_fetch)

    def detect(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized = normalize_snapshot_contract(snapshot)
        availability = normalized.get("availability", {}) or {}
        declared_missing = set(_ensure_str_list(availability.get("missing_fields")))
        notes = _ensure_str_list(availability.get("notes"))
        preflight = normalized.get("preflight", {}) or {}
        for row in _ensure_list(preflight.get("missing_data")):
            if isinstance(row, dict) and row.get("key"):
                declared_missing.add(str(row["key"]))

        candidates = _build_candidates(normalized, self._max_events)
        gaps: Dict[str, Dict[str, Any]] = {}

        def add_gap(field_path: str, reason: str, declared: bool) -> None:
            if not field_path:
                return
            reason_layer = self._reason_layer(field_path, declared, notes)
            supplementable, mcp_method, params_hint = self._supplement_plan(field_path, candidates)
            if reason_layer == REASON_LAYER_API_UNSUPPORTED:
                supplementable = False
                params_hint.setdefault("unresolved_reason", "current API/driver does not expose this field")
            if not supplementable and "unresolved_reason" not in params_hint:
                params_hint["unresolved_reason"] = "insufficient query key in snapshot"
            candidate = {
                "field_path": field_path,
                "reason": reason,
                "reason_layer": reason_layer,
                "supplementable": supplementable,
                "mcp_method": mcp_method,
                "params_hint": _stable_object(params_hint),
            }
            existing = gaps.get(field_path)
            if existing is None:
                gaps[field_path] = candidate
                return
            if existing["reason_layer"] != REASON_LAYER_SCHEMA_DECLARED and declared:
                gaps[field_path] = candidate
                return
            if (not existing["supplementable"]) and candidate["supplementable"]:
                gaps[field_path] = candidate

        for key in sorted(declared_missing):
            add_gap(key, "Declared in snapshot availability/preflight as missing.", True)

        if _is_timings_missing(normalized):
            add_gap("timings", "timings payload is empty or absent in snapshot.", False)

        if _is_pipelines_missing(normalized):
            add_gap("pipelines", "pipelines payload is empty or absent in snapshot.", False)
        else:
            if _pipeline_missing_render_targets(normalized):
                add_gap(
                    "pipelines.render_target_refs",
                    "one or more draw events miss pipeline render_target_refs details.",
                    False,
                )
            if _pipeline_missing_depth(normalized):
                add_gap(
                    "pipelines.depth_target_ref",
                    "one or more draw events miss pipeline depth_target_ref details.",
                    False,
                )

        if _shader_source_missing(normalized):
            if candidates["shader_query_targets"]:
                add_gap("shaders.source_high_level", "one or more shaders miss consumable source text.", False)
            else:
                add_gap(
                    "shaders.source_high_level",
                    "shader source text missing, but no queryable event_id/stage clue is available.",
                    False,
                )

        if self._implicit_texture_fetch and _texture_thumbnail_missing(normalized):
            if candidates["texture_resource_ids"]:
                add_gap(_TEXTURE_THUMBNAIL_FIELD, "one or more textures miss thumbnail payload.", False)
            else:
                add_gap(
                    _TEXTURE_THUMBNAIL_FIELD,
                    "texture thumbnail missing but no resource_id is available for query.",
                    False,
                )

        fields = sorted(gaps.keys(), key=lambda key: (_GAP_PRIORITY.get(key, 99), key))
        return [gaps[key] for key in fields]

    def _reason_layer(self, field_path: str, declared: bool, notes: Sequence[str]) -> str:
        if _has_unsupported_note(field_path, notes):
            return REASON_LAYER_API_UNSUPPORTED
        if declared:
            return REASON_LAYER_SCHEMA_DECLARED
        return REASON_LAYER_VALUE_MISSING

    def _supplement_plan(
        self, field_path: str, candidates: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        if field_path == "timings":
            return True, "get_action_timings", {}
        if field_path in _PIPELINE_GAP_FIELDS:
            events = candidates.get("pipeline_event_ids", [])
            if events:
                return True, "get_pipeline_state", {"event_id": "<required-int>", "candidates": events}
            return False, "get_pipeline_state", {"event_id": "<required-int>"}
        if field_path in _SHADER_GAP_FIELDS:
            targets = candidates.get("shader_query_targets", [])
            if targets:
                return True, "get_shader_info", {
                    "event_id": "<required-int>",
                    "stage": "<required-stage>",
                    "candidates": targets,
                }
            return False, "get_shader_info", {"event_id": "<required-int>", "stage": "<required-stage>"}
        if field_path == _TEXTURE_THUMBNAIL_FIELD:
            ids = candidates.get("texture_resource_ids", [])
            if ids:
                return True, "get_texture_data", {
                    "resource_id": "<required-str>",
                    "mip": 0,
                    "slice": 0,
                    "sample": 0,
                    "candidates": ids,
                }
            return False, "get_texture_data", {"resource_id": "<required-str>", "mip": 0, "slice": 0, "sample": 0}
        return False, None, {}


class MCPQueryPlanner:
    def __init__(self, max_events: int = 5, texture_query_limit: int = 32):
        self._max_events = max(1, int(max_events))
        self._texture_query_limit = max(1, int(texture_query_limit))

    def build(self, snapshot: Dict[str, Any], gaps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = normalize_snapshot_contract(snapshot)
        gap_fields = {str(gap.get("field_path")) for gap in gaps}
        candidates = _build_candidates(normalized, self._max_events)
        queries: List[QuerySpec] = []
        seen: set[Tuple[str, str]] = set()

        def add(method: str, params: Dict[str, Any], reason: str, field_path: str) -> None:
            stable_params = _stable_object(params)
            key = (method, json.dumps(stable_params, sort_keys=True, separators=(",", ":")))
            if key in seen:
                return
            seen.add(key)
            queries.append(QuerySpec(method=method, params=stable_params, reason=reason, field_path=field_path))

        if "timings" in gap_fields:
            add("get_action_timings", {}, "Fill missing timings in snapshot.", "timings")
        if gap_fields & _PIPELINE_GAP_FIELDS:
            for event_id in candidates["pipeline_event_ids"]:
                add("get_pipeline_state", {"event_id": int(event_id)}, "Fill pipeline/RT/depth state.", "pipelines")
        if gap_fields & _SHADER_GAP_FIELDS:
            for item in candidates["shader_query_targets"]:
                add(
                    "get_shader_info",
                    {"event_id": int(item["event_id"]), "stage": item["stage"]},
                    "Fill missing shader source text.",
                    "shaders.source_high_level",
                )
        if _TEXTURE_THUMBNAIL_FIELD in gap_fields:
            for resource_id in candidates["texture_resource_ids"][: self._texture_query_limit]:
                add(
                    "get_texture_data",
                    {"resource_id": str(resource_id), "mip": 0, "slice": 0, "sample": 0},
                    "Fill missing texture thumbnail data.",
                    _TEXTURE_THUMBNAIL_FIELD,
                )

        ordered = sorted(
            queries,
            key=lambda query: (
                _QUERY_PRIORITY.get(query.method, 99),
                json.dumps(query.params, sort_keys=True, separators=(",", ":")),
            ),
        )
        return [query.as_dict() for query in ordered]


def normalize_snapshot_contract(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _stable_object(snapshot or {})
    meta = normalized.get("meta", {}) or {}
    graphics_api = meta.get("graphics_api") or meta.get("driver")

    actions: List[Dict[str, Any]] = []
    legacy_pipeline_details: Dict[int, Dict[str, Any]] = {}
    for action in _ensure_list(normalized.get("actions")):
        if not isinstance(action, dict):
            continue
        row = dict(action)
        kind = _normalize_action_kind(row.get("kind"), row.get("type"))
        if kind:
            row["kind"] = kind
        event_id = _as_int(row.get("event_id"))
        if event_id is not None:
            detail: Dict[str, Any] = {}
            render_targets = row.get("render_targets")
            if _has_sequence_payload(render_targets):
                detail["render_target_refs"] = _ensure_list(render_targets)
            depth_target = row.get("depth_target")
            if _has_object_payload(depth_target):
                detail["depth_target_ref"] = depth_target
            if detail:
                legacy_pipeline_details[event_id] = detail
        actions.append(row)
    normalized["actions"] = actions

    shaders: List[Dict[str, Any]] = []
    for shader in _ensure_list(normalized.get("shaders")):
        if not isinstance(shader, dict):
            continue
        row = dict(shader)
        legacy_source = _clean_text(row.get("source_code"))
        if legacy_source and not _clean_text(row.get("source_high_level")) and not _clean_text(row.get("source_asm")):
            row["source_high_level"] = legacy_source
        shaders.append(row)
    normalized["shaders"] = shaders

    pipeline_rows: List[Dict[str, Any]] = []
    pipeline_event_ids: set[int] = set()
    for pipeline in _ensure_list(normalized.get("pipelines")):
        if not isinstance(pipeline, dict):
            continue
        row = dict(pipeline)
        event_id = _as_int(row.get("event_id"))
        if event_id is not None:
            pipeline_event_ids.add(event_id)
            legacy_detail = legacy_pipeline_details.get(event_id, {})
            if not _has_sequence_payload(row.get("render_target_refs")) and legacy_detail.get("render_target_refs") is not None:
                row["render_target_refs"] = _ensure_list(legacy_detail["render_target_refs"])
            if not _has_object_payload(row.get("depth_target_ref")) and legacy_detail.get("depth_target_ref") is not None:
                row["depth_target_ref"] = legacy_detail["depth_target_ref"]
        if graphics_api and not row.get("graphics_api"):
            row["graphics_api"] = graphics_api
        pipeline_rows.append(row)

    for event_id, legacy_detail in legacy_pipeline_details.items():
        if event_id in pipeline_event_ids:
            continue
        row: Dict[str, Any] = {"event_id": event_id}
        if graphics_api:
            row["graphics_api"] = graphics_api
        if legacy_detail.get("render_target_refs") is not None:
            row["render_target_refs"] = _ensure_list(legacy_detail["render_target_refs"])
        if legacy_detail.get("depth_target_ref") is not None:
            row["depth_target_ref"] = legacy_detail["depth_target_ref"]
        pipeline_rows.append(row)
    pipeline_rows.sort(key=lambda row: (_as_int(row.get("event_id")) is None, _as_int(row.get("event_id")) or 0))
    normalized["pipelines"] = pipeline_rows

    overview = normalized.get("overview", {}) or {}
    summary = overview.get("summary", {}) or {}
    if "draw_call_count" not in summary:
        summary["draw_call_count"] = sum(1 for action in actions if _is_draw_action(action))
    overview["summary"] = summary
    normalized["overview"] = overview

    return normalized


def inspect_bridge_state() -> Dict[str, Any]:
    ipc_dir = os.path.join(tempfile.gettempdir(), "renderdoc_mcp")
    request_file = os.path.join(ipc_dir, "request.json")
    response_file = os.path.join(ipc_dir, "response.json")
    lock_file = os.path.join(ipc_dir, "lock")
    return {
        "ipc_dir": ipc_dir,
        "ipc_dir_exists": os.path.isdir(ipc_dir),
        "request_present": os.path.exists(request_file),
        "response_present": os.path.exists(response_file),
        "lock_present": os.path.exists(lock_file),
        "request_age_seconds": _file_age_seconds(request_file),
        "response_age_seconds": _file_age_seconds(response_file),
    }


def build_mcp_envelope(
    *,
    ok: bool,
    data: Any,
    method: Optional[str],
    params: Dict[str, Any],
    availability: Optional[Dict[str, Any]] = None,
    evidence: Optional[List[Any]] = None,
    warnings: Optional[List[Any]] = None,
    recovery_hint: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
    source: str = "mcp",
) -> Dict[str, Any]:
    if availability is None:
        availability = {"status": "full", "missing_fields": [], "notes": []}
        if not ok:
            availability = {"status": "unavailable", "missing_fields": [], "notes": []}
    payload = {
        "ok": bool(ok),
        "contract_version": CONTRACT_VERSION,
        "data": data,
        "availability": _stable_object(availability),
        "evidence": _stable_object(evidence or []),
        "warnings": _stable_object(warnings or []),
        "recovery_hint": recovery_hint,
        "error": _stable_object(error) if error is not None else None,
        "method": method,
        "params": _stable_object(params or {}),
        "source": source,
    }
    return payload


def build_error_payload(
    *,
    code: str,
    message: str,
    method: Optional[str],
    params: Dict[str, Any],
    bridge_state: Optional[Dict[str, Any]] = None,
    capture_loaded: Optional[bool] = None,
) -> Dict[str, Any]:
    notes = _build_error_notes(code, bridge_state=bridge_state, capture_loaded=capture_loaded)
    return build_mcp_envelope(
        ok=False,
        data=None,
        method=method,
        params=params,
        availability={"status": "unavailable", "missing_fields": [], "notes": notes},
        error={"code": code, "message": message},
        recovery_hint=recovery_hint_for_error(
            code,
            method=method,
            bridge_state=bridge_state,
            capture_loaded=capture_loaded,
        ),
    )


def normalize_mcp_success(result: Any, *, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(result, dict) and "ok" in result and result.get("contract_version") == CONTRACT_VERSION:
        payload = dict(result)
        payload.setdefault("data", None)
        payload.setdefault("availability", {"status": "full", "missing_fields": [], "notes": []})
        payload.setdefault("evidence", [])
        payload.setdefault("warnings", [])
        payload.setdefault("recovery_hint", None)
        payload.setdefault("error", None)
        payload["method"] = method
        payload["params"] = _stable_object(params)
        payload["source"] = "mcp"
        return _annotate_success_payload(payload, method=method)

    availability = {"status": "full", "missing_fields": [], "notes": []}
    if isinstance(result, dict) and result.get("available") is False:
        availability = {"status": "partial", "missing_fields": [], "notes": ["query returned available=false"]}

    payload = build_mcp_envelope(
        ok=True,
        data=result,
        method=method,
        params=params,
        availability=availability,
    )
    return _annotate_success_payload(payload, method=method)


class MCPEnricher:
    def __init__(self, bridge_factory: Optional[Callable[[], Any]] = None):
        self._bridge_factory = bridge_factory or create_default_bridge

    def run(
        self,
        queries: Sequence[Dict[str, Any]],
        execute: bool = False,
        fanout: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "execute": bool(execute),
            "status": "dry_run",
            "query_results": [],
            "blockers": [],
            "recovery_hint": None,
            "bridge_call_count": 0,
            "contract_version": CONTRACT_VERSION,
            "health_probe": None,
            "fanout": _stable_object(fanout or {}),
        }
        if not queries:
            payload["status"] = "no_queries_needed"
            return payload
        if not execute:
            payload["status"] = "dry_run"
            return payload

        bridge_state = inspect_bridge_state()
        try:
            bridge = self._bridge_factory()
        except Exception as exc:
            code = "bridge_unavailable"
            probe = build_error_payload(
                code=code,
                message=str(exc),
                method="get_capture_status",
                params={},
                bridge_state=bridge_state,
            )
            payload["status"] = "blocked"
            payload["health_probe"] = probe
            payload["blockers"].append({"code": code, "message": str(exc)})
            payload["recovery_hint"] = probe.get("recovery_hint")
            return payload

        try:
            status_resp = _bridge_call(bridge, "get_capture_status", {})
            payload["bridge_call_count"] += 1
            probe = normalize_mcp_success(status_resp, method="get_capture_status", params={})
            payload["health_probe"] = probe
        except Exception as exc:
            code = classify_mcp_error(str(exc))
            probe = build_error_payload(
                code=code,
                message=str(exc),
                method="get_capture_status",
                params={},
                bridge_state=inspect_bridge_state(),
            )
            payload["status"] = "blocked"
            payload["health_probe"] = probe
            payload["blockers"].append({"code": code, "message": str(exc)})
            payload["recovery_hint"] = probe.get("recovery_hint")
            return payload

        if not _extract_capture_loaded(status_resp):
            code = "capture_not_loaded"
            payload["status"] = "blocked"
            payload["blockers"].append({"code": code, "message": "No active capture loaded in RenderDoc."})
            payload["recovery_hint"] = probe.get("recovery_hint") or recovery_hint_for_error(
                code,
                method="get_capture_status",
                capture_loaded=False,
            )
            return payload

        failures = 0
        for query in queries:
            method = str(query.get("method", ""))
            params = _stable_object(query.get("params", {}) or {})
            if not method:
                continue
            try:
                raw = _bridge_call(bridge, method, params)
                payload["bridge_call_count"] += 1
                payload["query_results"].append(normalize_mcp_success(raw, method=method, params=params))
            except Exception as exc:
                failures += 1
                payload["bridge_call_count"] += 1
                code = classify_mcp_error(str(exc))
                payload["query_results"].append(
                    build_error_payload(
                        code=code,
                        message=str(exc),
                        method=method,
                        params=params,
                        bridge_state=inspect_bridge_state() if code in ("bridge_unavailable", "timeout") else None,
                        capture_loaded=True,
                    )
                )

        if failures == 0:
            payload["status"] = "executed"
        elif failures < len(queries):
            payload["status"] = "partial"
            payload["recovery_hint"] = _last_recovery_hint(payload["query_results"])
        else:
            payload["status"] = "failed"
            payload["recovery_hint"] = _last_recovery_hint(payload["query_results"])
        return payload


class SkillMarkdownBuilder:
    def build(
        self,
        *,
        snapshot: Dict[str, Any],
        gaps: Sequence[Dict[str, Any]],
        queries: Sequence[Dict[str, Any]],
        commands: Sequence[str],
        enrichment: Dict[str, Any],
    ) -> str:
        normalized = normalize_snapshot_contract(snapshot)
        meta = normalized.get("meta", {}) or {}
        summary = (normalized.get("overview", {}) or {}).get("summary", {}) or {}
        fanout = enrichment.get("fanout", {}) or {}
        health_probe = enrichment.get("health_probe") or {}
        lines = [
            "# Skill Snapshot Consumer Brief",
            "",
            "## Snapshot Facts",
            "Source: snapshot.v1",
            f"- capture_name: {meta.get('capture_name', 'unknown')}",
            f"- graphics_api: {meta.get('graphics_api', meta.get('driver', 'unknown'))}",
            f"- schema_version: {normalized.get('schema_version', 'unknown')}",
            f"- action_count: {_summary_action_count(normalized, summary)}",
            "",
            "## Gap Analysis",
            "Source: snapshot.v1",
        ]
        if not gaps:
            lines.append("- No gaps detected. MCP supplement is not required.")
        else:
            lines.extend(
                [
                    "| field_path | reason_layer | supplementable | mcp_method | reason |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            for gap in gaps:
                lines.append(
                    f"| {gap.get('field_path', '')} | {gap.get('reason_layer', '')} | "
                    f"{str(gap.get('supplementable', False)).lower()} | {gap.get('mcp_method', '')} | "
                    f"{str(gap.get('reason', '')).replace('|', '/')} |"
                )
        lines.extend(["", "## MCP Supplement", "Source: MCP query"])
        lines.append(f"- execute: {bool(enrichment.get('execute', False))}")
        lines.append(f"- status: {enrichment.get('status', 'unknown')}")
        lines.append(f"- planned_queries: {fanout.get('detail_query_count', len(queries))}")
        lines.append(f"- command_count: {fanout.get('command_count', len(commands))}")
        lines.append(f"- bridge_calls: {int(enrichment.get('bridge_call_count', 0) or 0)}")
        if health_probe:
            lines.append(
                f"- health_probe: ok={health_probe.get('ok')} "
                f"loaded={_extract_capture_loaded(health_probe)}"
            )
        if enrichment.get("recovery_hint"):
            lines.append(f"- recovery_hint: {enrichment.get('recovery_hint')}")
        lines.extend(["", "## Command List"])
        if commands:
            for idx, command in enumerate(commands, 1):
                lines.append(f"{idx}. `{command}`")
        else:
            lines.append("- (empty)")
        return "\n".join(lines).strip() + "\n"


def analyze_snapshot(
    snapshot: Dict[str, Any],
    *,
    execute: bool = False,
    max_events: int = 5,
    texture_query_limit: int = 32,
    bridge_factory: Optional[Callable[[], Any]] = None,
    implicit_texture_fetch: bool = False,
) -> Dict[str, Any]:
    normalized = normalize_snapshot_contract(snapshot)
    gaps = SnapshotGapDetector(
        max_events=max_events,
        implicit_texture_fetch=implicit_texture_fetch,
    ).detect(normalized)
    queries = MCPQueryPlanner(max_events=max_events, texture_query_limit=texture_query_limit).build(normalized, gaps)
    commands = build_command_list(queries)
    fanout = _build_fanout_summary(
        queries,
        max_events=max_events,
        texture_query_limit=texture_query_limit,
        implicit_texture_fetch=implicit_texture_fetch,
    )
    enrichment = MCPEnricher(bridge_factory=bridge_factory).run(queries=queries, execute=execute, fanout=fanout)
    markdown = SkillMarkdownBuilder().build(
        snapshot=normalized,
        gaps=gaps,
        queries=queries,
        commands=commands,
        enrichment=enrichment,
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "gaps": gaps,
        "queries": queries,
        "commands": commands,
        "enrichment": enrichment,
        "fanout": fanout,
        "health_probe": enrichment.get("health_probe"),
        "markdown": markdown,
    }


def create_health_probe_command(python_cmd: str = "py -3") -> str:
    return f"{python_cmd} scripts/rdc_analyzer/mcp_examples/run_query.py --method get_capture_status --params '{{}}'"


def build_command_list(queries: Sequence[Dict[str, Any]], python_cmd: str = "py -3") -> List[str]:
    result: List[str] = [create_health_probe_command(python_cmd)]
    for query in queries:
        method = str(query.get("method", ""))
        params = _stable_object(query.get("params", {}) or {})
        params_json = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        result.append(
            f"{python_cmd} scripts/rdc_analyzer/mcp_examples/run_query.py --method {method} --params '{params_json}'"
        )
    return result


def create_default_bridge() -> Any:
    try:
        from mcp_server.bridge.client import RenderDocBridge  # type: ignore
    except Exception as exc:
        raise RuntimeError("mcp_server.bridge.client.RenderDocBridge is unavailable") from exc
    return RenderDocBridge()


def classify_mcp_error(message: str) -> str:
    text = (message or "").lower()
    if "cannot connect" in text or "bridge" in text:
        return "bridge_unavailable"
    if "no active capture" in text or ("capture" in text and "loaded" in text):
        return "capture_not_loaded"
    if "invalid argument" in text or ("invalid" in text and "param" in text):
        return "invalid_argument"
    if "not found" in text:
        return "not_found"
    if "unsupported" in text:
        return "unsupported_api"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    return "internal_error"


def recovery_hint_for_error(
    code: str,
    *,
    method: Optional[str] = None,
    bridge_state: Optional[Dict[str, Any]] = None,
    capture_loaded: Optional[bool] = None,
) -> str:
    if code == "bridge_unavailable":
        state = bridge_state or inspect_bridge_state()
        if not state.get("ipc_dir_exists"):
            return "Start RenderDoc GUI, enable the MCP Bridge extension, then retry get_capture_status."
        return "RenderDoc MCP bridge could not be created. Check the GUI extension install and restart RenderDoc."
    if code == "capture_not_loaded":
        return "Open a capture in qrenderdoc, then retry the detail query."
    if code == "invalid_argument":
        return "Check query params and retry."
    if code == "not_found":
        return "Verify event/resource identifiers and retry."
    if code == "unsupported_api":
        return "Current API/driver does not expose this field. Keep the snapshot gap and continue with other evidence."
    if code == "timeout":
        state = bridge_state or inspect_bridge_state()
        if state.get("ipc_dir_exists") and state.get("request_present") and not state.get("response_present"):
            return (
                "RenderDoc MCP IPC is present but no response was written. Check RenderDoc GUI, confirm the MCP "
                "Bridge extension is enabled, and verify the replay thread is not blocked, then retry get_capture_status."
            )
        return "Retry get_capture_status after checking RenderDoc GUI and MCP Bridge availability."
    if method == "get_capture_status" and capture_loaded is True:
        return "Capture is loaded. Detail queries can proceed."
    return "Check MCP bridge logs and retry."


def _annotate_success_payload(payload: Dict[str, Any], *, method: str) -> Dict[str, Any]:
    result = dict(payload)
    warnings = list(result.get("warnings") or [])
    if method == "get_capture_status":
        loaded = _extract_capture_loaded(result)
        if loaded:
            result["recovery_hint"] = result.get("recovery_hint") or recovery_hint_for_error(
                "internal_error",
                method=method,
                capture_loaded=True,
            )
        else:
            if "No active capture is loaded." not in warnings:
                warnings.append("No active capture is loaded.")
            result["recovery_hint"] = result.get("recovery_hint") or recovery_hint_for_error(
                "capture_not_loaded",
                method=method,
                capture_loaded=False,
            )
    result["warnings"] = _stable_object(warnings)
    return _stable_object(result)


def _build_error_notes(
    code: str,
    *,
    bridge_state: Optional[Dict[str, Any]] = None,
    capture_loaded: Optional[bool] = None,
) -> List[str]:
    notes: List[str] = []
    if code in ("bridge_unavailable", "timeout"):
        state = bridge_state or inspect_bridge_state()
        notes.append(f"ipc_dir_exists={str(bool(state.get('ipc_dir_exists'))).lower()}")
        notes.append(f"request_present={str(bool(state.get('request_present'))).lower()}")
        notes.append(f"response_present={str(bool(state.get('response_present'))).lower()}")
        notes.append(f"lock_present={str(bool(state.get('lock_present'))).lower()}")
    if code == "capture_not_loaded" or capture_loaded is False:
        notes.append("No active capture is loaded.")
    return notes


def _build_fanout_summary(
    queries: Sequence[Dict[str, Any]],
    *,
    max_events: int,
    texture_query_limit: int,
    implicit_texture_fetch: bool,
) -> Dict[str, Any]:
    detail_methods: Dict[str, int] = {}
    for query in queries:
        method = str(query.get("method", ""))
        detail_methods[method] = detail_methods.get(method, 0) + 1
    return {
        "max_events": int(max_events),
        "texture_query_limit": int(texture_query_limit),
        "implicit_texture_fetch": bool(implicit_texture_fetch),
        "detail_query_count": len(queries),
        "detail_methods": detail_methods,
        "command_count": len(queries) + 1,
    }


def _last_recovery_hint(results: Sequence[Dict[str, Any]]) -> Optional[str]:
    for row in reversed(list(results)):
        hint = row.get("recovery_hint")
        if hint:
            return str(hint)
    return None


def _bridge_call(bridge: Any, method: str, params: Dict[str, Any]) -> Any:
    attempts = 3
    for idx in range(attempts):
        try:
            return bridge.call(method, params)
        except TypeError:
            if params:
                raise
            return bridge.call(method)
        except Exception as exc:
            text = str(exc)
            is_lock_conflict = "WinError 32" in text or "response.json" in text
            if (not is_lock_conflict) or idx == attempts - 1:
                raise
            time.sleep(0.05 * (idx + 1))
    raise RuntimeError("unreachable")


def _extract_capture_loaded(payload: Any) -> bool:
    if isinstance(payload, dict):
        if "ok" in payload and isinstance(payload.get("data"), dict):
            return bool((payload.get("data") or {}).get("loaded", False))
        return bool(payload.get("loaded", False))
    return False


def _build_candidates(snapshot: Dict[str, Any], max_events: int) -> Dict[str, Any]:
    actions = _ensure_list(snapshot.get("actions"))
    shaders = _ensure_list(snapshot.get("shaders"))
    textures = _ensure_list((snapshot.get("resources", {}) or {}).get("textures"))

    pipeline_event_ids = sorted(
        {
            _as_int(action.get("event_id"))
            for action in actions
            if isinstance(action, dict) and _is_draw_action(action) and _as_int(action.get("event_id")) is not None
        }
    )[:max_events]

    shader_targets = sorted(
        {
            (
                _as_int(shader.get("event_id"))
                if _as_int(shader.get("event_id")) is not None
                else _as_int(shader.get("bound_event_id")),
                str(shader.get("stage", "")).strip().lower(),
            )
            for shader in shaders
            if isinstance(shader, dict) and _shader_needs_source(shader)
        },
        key=lambda row: (row[0] if row[0] is not None else 10**9, row[1]),
    )
    shader_query_targets = [
        {"event_id": row[0], "stage": row[1]}
        for row in shader_targets
        if row[0] is not None and row[1] in _VALID_SHADER_STAGES
    ]

    texture_resource_ids = sorted(
        {
            str(texture.get("resource_id"))
            for texture in textures
            if isinstance(texture, dict)
            and _texture_needs_thumbnail(texture)
            and texture.get("resource_id")
        }
    )

    return {
        "pipeline_event_ids": pipeline_event_ids,
        "shader_query_targets": shader_query_targets,
        "texture_resource_ids": texture_resource_ids,
    }


def _normalize_action_kind(kind: Any, legacy_type: Any) -> str:
    text = _clean_text(kind) or _clean_text(legacy_type)
    if not text:
        return ""
    lower = text.lower()
    if "dispatch" in lower:
        return "dispatch"
    if "clear" in lower:
        return "clear"
    if "marker" in lower:
        return "marker"
    return "draw"


def _is_draw_action(action: Dict[str, Any]) -> bool:
    kind = _normalize_action_kind(action.get("kind"), action.get("type"))
    return (not kind) or kind == "draw"


def _has_unsupported_note(field_path: str, notes: Sequence[str]) -> bool:
    keys = [row for row in field_path.replace("[]", "").split(".") if row]
    for note in notes:
        lower = note.lower()
        if not any(key in lower for key in _UNSUPPORTED_HINT_KEYWORDS):
            continue
        if not keys or any(key.lower() in lower for key in keys):
            return True
    return False


def _is_timings_missing(snapshot: Dict[str, Any]) -> bool:
    timings = snapshot.get("timings")
    return timings is None or (isinstance(timings, dict) and not timings)


def _is_pipelines_missing(snapshot: Dict[str, Any]) -> bool:
    pipelines = snapshot.get("pipelines")
    return pipelines is None or (isinstance(pipelines, list) and len(pipelines) == 0)


def _pipeline_missing_render_targets(snapshot: Dict[str, Any]) -> bool:
    pipeline_index = _pipeline_index(snapshot)
    for action in _ensure_list(snapshot.get("actions")):
        if not isinstance(action, dict) or not _is_draw_action(action):
            continue
        event_id = _as_int(action.get("event_id"))
        if event_id is None:
            continue
        pipeline = pipeline_index.get(event_id, {})
        if not _has_sequence_payload(pipeline.get("render_target_refs")):
            return True
    return False


def _pipeline_missing_depth(snapshot: Dict[str, Any]) -> bool:
    pipeline_index = _pipeline_index(snapshot)
    for action in _ensure_list(snapshot.get("actions")):
        if not isinstance(action, dict) or not _is_draw_action(action):
            continue
        event_id = _as_int(action.get("event_id"))
        if event_id is None:
            continue
        pipeline = pipeline_index.get(event_id, {})
        if not _has_object_payload(pipeline.get("depth_target_ref")):
            return True
    return False


def _pipeline_index(snapshot: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for pipeline in _ensure_list(snapshot.get("pipelines")):
        if not isinstance(pipeline, dict):
            continue
        event_id = _as_int(pipeline.get("event_id"))
        if event_id is not None:
            result[event_id] = pipeline
    return result


def _shader_source_missing(snapshot: Dict[str, Any]) -> bool:
    for shader in _ensure_list(snapshot.get("shaders")):
        if isinstance(shader, dict) and _shader_needs_source(shader):
            return True
    return False


def _shader_needs_source(shader: Dict[str, Any]) -> bool:
    return not (_clean_text(shader.get("source_high_level")) or _clean_text(shader.get("source_asm")))


def _texture_thumbnail_missing(snapshot: Dict[str, Any]) -> bool:
    textures = _ensure_list((snapshot.get("resources", {}) or {}).get("textures"))
    for texture in textures:
        if isinstance(texture, dict) and _texture_needs_thumbnail(texture):
            return True
    return False


def _texture_needs_thumbnail(texture: Dict[str, Any]) -> bool:
    thumbnail = texture.get("thumbnail")
    return not isinstance(thumbnail, str) or not thumbnail.strip()


def _summary_action_count(snapshot: Dict[str, Any], summary: Dict[str, Any]) -> int:
    draw_call_count = _as_int(summary.get("draw_call_count"))
    if draw_call_count is not None:
        return draw_call_count
    action_count = _as_int(summary.get("action_count"))
    if action_count is not None:
        return action_count
    legacy_actions = _as_int(summary.get("actions"))
    if legacy_actions is not None:
        return legacy_actions
    return len(_ensure_list(snapshot.get("actions")))


def _has_sequence_payload(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _has_object_payload(value: Any) -> bool:
    return isinstance(value, dict)


def _file_age_seconds(path: str) -> Optional[float]:
    try:
        if not os.path.exists(path):
            return None
        return max(0.0, time.time() - os.path.getmtime(path))
    except Exception:
        return None


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _ensure_str_list(value: Any) -> List[str]:
    return [str(row).strip() for row in _ensure_list(value) if str(row).strip()]


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _stable_object(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
