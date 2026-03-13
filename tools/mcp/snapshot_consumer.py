from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


CONTRACT_VERSION = "mcp-query.v1"

REASON_LAYER_SCHEMA_DECLARED = "schema_declared_gap"
REASON_LAYER_VALUE_MISSING = "value_missing"
REASON_LAYER_API_UNSUPPORTED = "api_not_supported"

_UNSUPPORTED_HINT_KEYWORDS = ("unsupported", "not supported", "not expose", "unavailable")
_VALID_SHADER_STAGES = {"vertex", "hull", "domain", "geometry", "pixel", "compute"}
_GAP_PRIORITY = {
    "timings": 0,
    "pipelines": 1,
    "actions[].render_targets": 2,
    "actions[].depth_target": 3,
    "shaders.source_code": 4,
    "resources.textures.thumbnail": 5,
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
    def __init__(self, max_events: int = 5):
        self._max_events = max(1, int(max_events))

    def detect(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        availability = snapshot.get("availability", {}) or {}
        declared_missing = set(_ensure_str_list(availability.get("missing_fields")))
        notes = _ensure_str_list(availability.get("notes"))
        preflight = snapshot.get("preflight", {}) or {}
        for row in _ensure_list(preflight.get("missing_data")):
            if isinstance(row, dict) and row.get("key"):
                declared_missing.add(str(row["key"]))

        candidates = _build_candidates(snapshot, self._max_events)
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

        if _is_timings_missing(snapshot):
            add_gap("timings", "timings payload is empty or absent in snapshot.", False)
        if _is_pipelines_missing(snapshot):
            add_gap("pipelines", "pipelines payload is empty or absent in snapshot.", False)
        if _draw_action_missing_rt(snapshot):
            add_gap("actions[].render_targets", "one or more draw actions miss render_targets details.", False)
        if _draw_action_missing_depth(snapshot):
            add_gap("actions[].depth_target", "one or more draw actions miss depth_target details.", False)
        if _shader_source_missing(snapshot):
            if candidates["shader_query_targets"]:
                add_gap("shaders.source_code", "one or more shaders miss source_code.", False)
            else:
                add_gap(
                    "shaders.source_code",
                    "shader source_code missing, but no queryable event_id/stage clue is available.",
                    False,
                )
        if _texture_thumbnail_missing(snapshot):
            if candidates["texture_resource_ids"]:
                add_gap("resources.textures.thumbnail", "one or more textures miss thumbnail payload.", False)
            else:
                add_gap(
                    "resources.textures.thumbnail",
                    "texture thumbnail missing but no resource_id is available for query.",
                    False,
                )

        fields = sorted(gaps.keys(), key=lambda k: (_GAP_PRIORITY.get(k, 99), k))
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
        if field_path in ("pipelines", "actions[].render_targets", "actions[].depth_target"):
            events = candidates.get("pipeline_event_ids", [])
            if events:
                return True, "get_pipeline_state", {"event_id": "<required-int>", "candidates": events}
            return False, "get_pipeline_state", {"event_id": "<required-int>"}
        if field_path == "shaders.source_code":
            targets = candidates.get("shader_query_targets", [])
            if targets:
                return True, "get_shader_info", {
                    "event_id": "<required-int>",
                    "stage": "<required-stage>",
                    "candidates": targets,
                }
            return False, "get_shader_info", {"event_id": "<required-int>", "stage": "<required-stage>"}
        if field_path == "resources.textures.thumbnail":
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
        gap_fields = {str(g.get("field_path")) for g in gaps}
        candidates = _build_candidates(snapshot, self._max_events)
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
        if {"pipelines", "actions[].render_targets", "actions[].depth_target"} & gap_fields:
            for event_id in candidates["pipeline_event_ids"]:
                add("get_pipeline_state", {"event_id": int(event_id)}, "Fill pipeline/RT/depth state.", "pipelines")
        if "shaders.source_code" in gap_fields:
            for item in candidates["shader_query_targets"]:
                add(
                    "get_shader_info",
                    {"event_id": int(item["event_id"]), "stage": item["stage"]},
                    "Fill missing shader source code.",
                    "shaders.source_code",
                )
        if "resources.textures.thumbnail" in gap_fields:
            for rid in candidates["texture_resource_ids"][: self._texture_query_limit]:
                add(
                    "get_texture_data",
                    {"resource_id": str(rid), "mip": 0, "slice": 0, "sample": 0},
                    "Fill missing texture thumbnail data.",
                    "resources.textures.thumbnail",
                )

        ordered = sorted(
            queries,
            key=lambda q: (
                _QUERY_PRIORITY.get(q.method, 99),
                json.dumps(q.params, sort_keys=True, separators=(",", ":")),
            ),
        )
        return [q.as_dict() for q in ordered]


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
        return _stable_object(payload)
    availability = {"status": "full", "missing_fields": [], "notes": []}
    if isinstance(result, dict) and result.get("available") is False:
        availability = {"status": "partial", "missing_fields": [], "notes": ["query returned available=false"]}
    return build_mcp_envelope(ok=True, data=result, method=method, params=params, availability=availability)


class MCPEnricher:
    def __init__(self, bridge_factory: Optional[Callable[[], Any]] = None):
        self._bridge_factory = bridge_factory or create_default_bridge

    def run(self, queries: Sequence[Dict[str, Any]], execute: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "execute": bool(execute),
            "status": "dry_run",
            "query_results": [],
            "blockers": [],
            "recovery_hint": None,
            "bridge_call_count": 0,
            "contract_version": CONTRACT_VERSION,
        }
        if not queries:
            payload["status"] = "no_queries_needed"
            return payload
        if not execute:
            payload["status"] = "dry_run"
            return payload
        try:
            bridge = self._bridge_factory()
        except Exception as exc:
            code = "bridge_unavailable"
            payload["status"] = "blocked"
            payload["blockers"].append({"code": code, "message": str(exc)})
            payload["recovery_hint"] = recovery_hint_for_error(code)
            return payload

        try:
            status_resp = _bridge_call(bridge, "get_capture_status", {})
            payload["bridge_call_count"] += 1
        except Exception as exc:
            code = classify_mcp_error(str(exc))
            payload["status"] = "blocked"
            payload["blockers"].append({"code": code, "message": str(exc)})
            payload["recovery_hint"] = recovery_hint_for_error(code)
            return payload

        if not _extract_capture_loaded(status_resp):
            code = "capture_not_loaded"
            payload["status"] = "blocked"
            payload["blockers"].append({"code": code, "message": "No active capture loaded in RenderDoc."})
            payload["recovery_hint"] = recovery_hint_for_error(code)
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
                    build_mcp_envelope(
                        ok=False,
                        data=None,
                        method=method,
                        params=params,
                        error={"code": code, "message": str(exc)},
                        recovery_hint=recovery_hint_for_error(code),
                    )
                )

        if failures == 0:
            payload["status"] = "executed"
        elif failures < len(queries):
            payload["status"] = "partial"
            payload["recovery_hint"] = payload["query_results"][-1].get("recovery_hint")
        else:
            payload["status"] = "failed"
            payload["recovery_hint"] = payload["query_results"][-1].get("recovery_hint")
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
        meta = snapshot.get("meta", {}) or {}
        summary = (snapshot.get("overview", {}) or {}).get("summary", {}) or {}
        lines = [
            "# Skill Snapshot Consumer Brief",
            "",
            "## Snapshot Facts",
            "Source: snapshot.v1",
            f"- capture_name: {meta.get('capture_name', 'unknown')}",
            f"- graphics_api: {meta.get('graphics_api', meta.get('driver', 'unknown'))}",
            f"- schema_version: {snapshot.get('schema_version', 'unknown')}",
            f"- action_count: {summary.get('actions', len(_ensure_list(snapshot.get('actions'))))}",
            "",
            "## Gap Analysis",
            "Source: snapshot.v1",
        ]
        if not gaps:
            lines.append("- No gaps detected. MCP supplement is not required.")
        else:
            lines.extend(["| field_path | reason_layer | supplementable | mcp_method | reason |", "| --- | --- | --- | --- | --- |"])
            for gap in gaps:
                lines.append(
                    f"| {gap.get('field_path','')} | {gap.get('reason_layer','')} | {str(gap.get('supplementable',False)).lower()} | {gap.get('mcp_method','')} | {str(gap.get('reason','')).replace('|','/')} |"
                )
        lines.extend(["", "## MCP Supplement", "Source: MCP query"])
        lines.append(f"- execute: {bool(enrichment.get('execute', False))}")
        lines.append(f"- status: {enrichment.get('status', 'unknown')}")
        lines.append(f"- planned_queries: {len(queries)}")
        lines.append(f"- bridge_calls: {int(enrichment.get('bridge_call_count', 0) or 0)}")
        if enrichment.get("recovery_hint"):
            lines.append(f"- recovery_hint: {enrichment.get('recovery_hint')}")
        lines.extend(["", "## Command List"])
        if commands:
            for idx, cmd in enumerate(commands, 1):
                lines.append(f"{idx}. `{cmd}`")
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
) -> Dict[str, Any]:
    gaps = SnapshotGapDetector(max_events=max_events).detect(snapshot)
    queries = MCPQueryPlanner(max_events=max_events, texture_query_limit=texture_query_limit).build(snapshot, gaps)
    commands = build_command_list(queries)
    enrichment = MCPEnricher(bridge_factory=bridge_factory).run(queries=queries, execute=execute)
    markdown = SkillMarkdownBuilder().build(
        snapshot=snapshot,
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
        "markdown": markdown,
    }


def build_command_list(queries: Sequence[Dict[str, Any]], python_cmd: str = "py -3") -> List[str]:
    result: List[str] = []
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


def recovery_hint_for_error(code: str) -> str:
    if code == "bridge_unavailable":
        return "Start RenderDoc MCP bridge extension and retry."
    if code == "capture_not_loaded":
        return "Open a capture in qrenderdoc and retry."
    if code == "invalid_argument":
        return "Check query params and retry."
    if code == "not_found":
        return "Verify event/resource identifiers and retry."
    if code == "unsupported_api":
        return "Current API/driver does not expose this field."
    if code == "timeout":
        return "Retry with a smaller query scope."
    return "Check MCP bridge logs and retry."


def _bridge_call(bridge: Any, method: str, params: Dict[str, Any]) -> Any:
    # File-based IPC occasionally hits transient response file lock conflicts
    # on Windows. Retry a few times before bubbling up.
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
    pipeline_ids = sorted({_as_int(a.get("event_id")) for a in actions if isinstance(a, dict) and _is_draw_action(a) and _as_int(a.get("event_id")) is not None})[:max_events]
    shader_targets = sorted(
        {( _as_int(s.get("event_id")) if _as_int(s.get("event_id")) is not None else _as_int(s.get("bound_event_id")), str(s.get("stage","")).strip().lower())
         for s in shaders
         if isinstance(s, dict) and (not isinstance(s.get("source_code"), str) or not s.get("source_code").strip())},
        key=lambda t: (t[0] if t[0] is not None else 10**9, t[1]),
    )
    shader_targets = [{"event_id": t[0], "stage": t[1]} for t in shader_targets if t[0] is not None and t[1] in _VALID_SHADER_STAGES]
    texture_ids = sorted({str(t.get("resource_id")) for t in textures if isinstance(t, dict) and (not isinstance(t.get("thumbnail"), str) or not t.get("thumbnail").strip()) and t.get("resource_id")})
    return {"pipeline_event_ids": pipeline_ids, "shader_query_targets": shader_targets, "texture_resource_ids": texture_ids}


def _is_draw_action(action: Dict[str, Any]) -> bool:
    action_type = str(action.get("type", "")).lower()
    return (not action_type) or action_type == "draw"


def _has_unsupported_note(field_path: str, notes: Sequence[str]) -> bool:
    keys = [x for x in field_path.replace("[]", "").split(".") if x]
    for note in notes:
        lower = note.lower()
        if not any(k in lower for k in _UNSUPPORTED_HINT_KEYWORDS):
            continue
        if not keys or any(k.lower() in lower for k in keys):
            return True
    return False


def _is_timings_missing(snapshot: Dict[str, Any]) -> bool:
    t = snapshot.get("timings")
    return t is None or (isinstance(t, dict) and not t)


def _is_pipelines_missing(snapshot: Dict[str, Any]) -> bool:
    p = snapshot.get("pipelines")
    return p is None or (isinstance(p, list) and len(p) == 0)


def _draw_action_missing_rt(snapshot: Dict[str, Any]) -> bool:
    for action in _ensure_list(snapshot.get("actions")):
        if isinstance(action, dict) and _is_draw_action(action):
            if "render_targets" not in action or action.get("render_targets") is None:
                return True
    return False


def _draw_action_missing_depth(snapshot: Dict[str, Any]) -> bool:
    for action in _ensure_list(snapshot.get("actions")):
        if isinstance(action, dict) and _is_draw_action(action):
            if "depth_target" not in action or action.get("depth_target") is None:
                return True
    return False


def _shader_source_missing(snapshot: Dict[str, Any]) -> bool:
    for shader in _ensure_list(snapshot.get("shaders")):
        if isinstance(shader, dict):
            src = shader.get("source_code")
            if not isinstance(src, str) or not src.strip():
                return True
    return False


def _texture_thumbnail_missing(snapshot: Dict[str, Any]) -> bool:
    textures = _ensure_list((snapshot.get("resources", {}) or {}).get("textures"))
    for texture in textures:
        if isinstance(texture, dict):
            thumb = texture.get("thumbnail")
            if not isinstance(thumb, str) or not thumb.strip():
                return True
    return False


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _ensure_str_list(value: Any) -> List[str]:
    return [str(v).strip() for v in _ensure_list(value) if str(v).strip()]


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _stable_object(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
