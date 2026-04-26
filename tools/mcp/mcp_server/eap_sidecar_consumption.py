from __future__ import annotations

from typing import Any, Dict, List, Mapping


DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 100


def count_eap_sections(payload: Dict[str, Any]) -> Dict[str, int]:
    render_graph = payload.get("render_graph", {}) if isinstance(payload.get("render_graph"), dict) else {}
    rules = payload.get("rules", {}) if isinstance(payload.get("rules"), dict) else {}
    return {
        "render_graph_nodes": len(_dict_list(render_graph.get("nodes"))),
        "commands": len(_dict_list(payload.get("commands"))),
        "resources": len(_dict_list(payload.get("resources"))),
        "assets": len(_dict_list(payload.get("assets"))),
        "materials": len(_dict_list(payload.get("materials"))),
        "shaders": len(_dict_list(payload.get("shaders"))),
        "pipelines": len(_dict_list(payload.get("pipelines"))),
        "rule_results": len(_dict_list(rules.get("results"))),
    }


def search_commands_data(
    payload: Dict[str, Any],
    *,
    filters: Mapping[str, str],
    limit: int,
) -> Dict[str, Any]:
    commands = _dict_list(payload.get("commands"))
    matched = []
    for command in commands:
        matched_by = _command_matched_by(command, filters)
        if matched_by:
            item = _summarize_command(command)
            item["matched_by"] = matched_by
            matched.append(item)

    return {
        "query": dict(filters),
        "match_count": len(matched),
        "items": matched[:limit],
        "truncated": len(matched) > limit,
    }


def rule_results_data(
    payload: Dict[str, Any],
    *,
    severity: str,
    limit: int,
) -> Dict[str, Any]:
    requested_severity = str(severity).strip().lower()
    rules = payload.get("rules", {}) if isinstance(payload.get("rules"), dict) else {}
    results = _dict_list(rules.get("results"))
    matched = []
    for result in results:
        result_severity = str(result.get("severity", "")).strip().lower()
        if requested_severity and result_severity != requested_severity:
            continue
        matched.append(_summarize_rule_result(result))

    return {
        "severity": requested_severity or None,
        "result_count": len(matched),
        "items": matched[:limit],
        "truncated": len(matched) > limit,
    }


def normalize_limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_SEARCH_LIMIT
    return max(1, min(value, MAX_SEARCH_LIMIT))


def _dict_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _command_matched_by(command: Dict[str, Any], filters: Mapping[str, str]) -> List[str]:
    matched_by = []
    query = filters.get("query", "")
    if query and query.lower() in _command_search_text(command).lower():
        matched_by.append("query")
    for field_name in ("pass_id", "material_id", "pipeline_id"):
        expected = filters.get(field_name, "")
        if expected and str(command.get(field_name, "")) == expected:
            matched_by.append(field_name)
    for field_name in ("resource_id", "shader_id"):
        expected = filters.get(field_name, "")
        if expected and expected in _command_id_values(command, field_name):
            matched_by.append(field_name)
    if not any(filters.values()):
        matched_by.append("unfiltered")
    return matched_by


def _command_search_text(command: Dict[str, Any]) -> str:
    parts = []
    for key in (
        "id",
        "name",
        "kind",
        "pass_id",
        "material_id",
        "pipeline_id",
        "resource_id",
        "shader_id",
        "event_id",
    ):
        value = command.get(key)
        if value is not None:
            parts.append(str(value))
    for key in ("resource_ids", "shader_ids"):
        parts.extend(_string_list(command.get(key)))
    return " ".join(parts)


def _summarize_command(command: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in (
        "id",
        "event_id",
        "name",
        "kind",
        "pass_id",
        "material_id",
        "pipeline_id",
    ):
        if key in command:
            summary[key] = command.get(key)
    for key in ("resource_ids", "shader_ids"):
        values = _string_list(command.get(key))
        if values:
            summary[key] = values
    return summary


def _summarize_rule_result(result: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in (
        "id",
        "severity",
        "title",
        "message",
        "command_id",
        "resource_id",
        "pass_id",
    ):
        if key in result:
            summary[key] = result.get(key)
    evidence_refs = _string_list(result.get("evidence_refs"))
    if evidence_refs:
        summary["evidence_refs"] = evidence_refs
    return summary


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _command_id_values(command: Dict[str, Any], field_name: str) -> List[str]:
    values = _string_list(command.get(field_name))
    values.extend(_string_list(command.get(f"{field_name}s")))
    return values
