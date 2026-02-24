from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class BundleData:
    events: List[Dict[str, Any]]
    textures: List[Dict[str, Any]]
    shaders: List[Dict[str, Any]]
    stats: Dict[str, Any]
    shader_usage: Dict[str, List[int]]


def _normalize_draw_type(draw_type: Optional[str]) -> str:
    if not draw_type:
        return "draw"
    return str(draw_type).strip().lower()


def _extract_shader(binding: Optional[Dict[str, Any]], stage: str) -> Optional[Dict[str, Any]]:
    if not binding:
        return None
    shader_id = binding.get("shader_resource_id")
    if shader_id is None:
        shader_id = binding.get("shader_id")
    name = binding.get("shader_name") or binding.get("name") or stage
    if shader_id is None and name is None:
        return None
    return {"id": shader_id, "name": name, "stage": stage}


def _record_shader(
    shader: Dict[str, Any],
    shaders: List[Dict[str, Any]],
    seen: Set[Tuple[Any, str, Any]],
    shader_usage: Dict[str, List[int]],
    eid: Optional[int],
) -> None:
    key = (shader.get("id"), shader.get("stage"), shader.get("name"))
    if key not in seen:
        seen.add(key)
        shaders.append(shader)
    shader_id = shader.get("id")
    if shader_id is None or eid is None:
        return
    shader_usage.setdefault(str(shader_id), []).append(int(eid))


def analysis_to_bundle(analysis: Dict[str, Any]) -> BundleData:
    draw_calls = analysis.get("draw_calls") or analysis.get("events") or []
    events: List[Dict[str, Any]] = []
    shaders: List[Dict[str, Any]] = []
    textures: List[Dict[str, Any]] = analysis.get("textures") or []
    stats: Dict[str, Any] = {}
    shader_usage: Dict[str, List[int]] = {}
    seen_shaders: Set[Tuple[Any, str, Any]] = set()

    summary = analysis.get("summary") or analysis.get("stats") or {}
    if isinstance(summary, dict):
        stats.update(summary)
    if "draw_calls" not in stats:
        stats["draw_calls"] = len(draw_calls)

    for draw in draw_calls:
        if not isinstance(draw, dict):
            continue
        eid = draw.get("event_id") or draw.get("eid") or draw.get("eventId")
        draw_type = draw.get("draw_type") or draw.get("type")
        event_type = _normalize_draw_type(draw_type)

        event: Dict[str, Any] = {
            "eid": eid,
            "name": draw.get("name") or draw.get("label") or "",
            "type": event_type,
        }
        if "vertex_count" in draw:
            event["vertexCount"] = draw.get("vertex_count")
        if "instance_count" in draw:
            event["instanceCount"] = draw.get("instance_count")

        pipeline_state = draw.get("pipeline_state") or draw.get("pipelineState") or {}
        if isinstance(pipeline_state, dict) and pipeline_state:
            pipeline_state_out: Dict[str, Any] = {}
            vs_binding = pipeline_state.get("vs_bindings") or pipeline_state.get("vs")
            ps_binding = pipeline_state.get("ps_bindings") or pipeline_state.get("ps")
            if vs_binding:
                pipeline_state_out["vs"] = vs_binding
            if ps_binding:
                pipeline_state_out["ps"] = ps_binding
            if pipeline_state_out:
                event["pipelineState"] = pipeline_state_out

            vs_shader = _extract_shader(vs_binding, "VS")
            ps_shader = _extract_shader(ps_binding, "PS")
            if vs_shader:
                _record_shader(vs_shader, shaders, seen_shaders, shader_usage, eid)
            if ps_shader:
                _record_shader(ps_shader, shaders, seen_shaders, shader_usage, eid)

        events.append(event)

    return BundleData(
        events=events,
        textures=textures,
        shaders=shaders,
        stats=stats,
        shader_usage=shader_usage,
    )
