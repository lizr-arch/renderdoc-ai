from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class BundleData:
    events: List[Dict[str, Any]]
    textures: List[Dict[str, Any]]
    shaders: List[Dict[str, Any]]
    stats: Dict[str, Any]
    shader_usage: Dict[str, List[Dict[str, Any]]]


def _normalize_draw_type(draw_type: Optional[str]) -> str:
    if not draw_type:
        return "draw"
    return str(draw_type).strip().lower()


def _parse_resource_id(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    if text.startswith("ResourceId::"):
        text = text[len("ResourceId::") :]
    if text in ("Null()", "0", "0()"):
        return None
    try:
        return int(text)
    except ValueError:
        return value


def _extract_shader(binding: Optional[Dict[str, Any]], stage: str) -> Optional[Dict[str, Any]]:
    if not binding:
        return None
    shader_id = binding.get("shader_resource_id")
    if shader_id is None:
        shader_id = binding.get("shader_id")
    if shader_id is None:
        shader_id = binding.get("resourceId")
    if shader_id is None:
        shader_id = binding.get("id")
    name = binding.get("shader_name") or binding.get("name") or stage
    if shader_id is None and name is None:
        return None
    return {"id": shader_id, "name": name, "stage": stage}


def _normalize_shader_ids(shader: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    shader_id = shader.get("id")
    if shader_id is None:
        shader_id = shader.get("resource_id")
    if shader_id is None:
        shader_id = shader.get("resourceId")
    shader_id = _parse_resource_id(shader_id)
    if shader_id in (None, 0):
        return None
    if "id" not in shader:
        shader["id"] = shader_id
    if "resource_id" not in shader:
        shader["resource_id"] = shader_id
    return shader


def _normalize_texture_ids(texture: Dict[str, Any]) -> None:
    resource_id = texture.get("resource_id")
    if resource_id is None:
        resource_id = texture.get("resourceId")
    if resource_id is None:
        resource_id = texture.get("id")
    if resource_id is None:
        return
    if "resource_id" not in texture:
        texture["resource_id"] = resource_id
    if "id" not in texture:
        texture["id"] = resource_id


def _record_shader(
    shader: Dict[str, Any],
    shaders: List[Dict[str, Any]],
    seen: Set[Tuple[Any, str, Any]],
    shader_usage: Dict[str, List[Dict[str, Any]]],
    eid: Optional[int],
    draw_name: Optional[str] = None,
) -> None:
    shader = _normalize_shader_ids(shader)
    if shader is None:
        return
    key = (shader.get("id"), shader.get("stage"), shader.get("name"))
    if key not in seen:
        seen.add(key)
        shaders.append(shader)
    shader_id = shader.get("id")
    if shader_id is None or eid is None:
        return
    shader_usage.setdefault(str(shader_id), []).append(
        {
            "event_id": int(eid),
            "name": draw_name or "Draw Call",
            "slot": 0,
        }
    )


def _record_shader_usage(
    shader_usage: Dict[str, List[Dict[str, Any]]],
    shader_id: Any,
    eid: Optional[int],
    draw_name: Optional[str] = None,
) -> None:
    if eid is None:
        return
    shader_id = _parse_resource_id(shader_id)
    if shader_id in (None, 0):
        return
    try:
        event_id = int(eid)
    except Exception:
        return
    shader_usage.setdefault(str(shader_id), []).append(
        {
            "event_id": event_id,
            "name": draw_name or "Draw Call",
            "slot": 0,
        }
    )


def analysis_to_bundle(analysis: Dict[str, Any]) -> BundleData:
    draw_calls = analysis.get("draw_calls") or analysis.get("events") or []
    events: List[Dict[str, Any]] = []
    shaders: List[Dict[str, Any]] = []
    textures: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {}
    shader_usage: Dict[str, List[Dict[str, Any]]] = {}
    seen_shaders: Set[Tuple[Any, str, Any]] = set()

    for texture in analysis.get("textures") or []:
        if not isinstance(texture, dict):
            continue
        _normalize_texture_ids(texture)
        textures.append(texture)

    for shader in analysis.get("shaders") or []:
        if not isinstance(shader, dict):
            continue
        _record_shader(shader, shaders, seen_shaders, shader_usage, None)

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
        draw_name = draw.get("name") or draw.get("label") or ""
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
                _record_shader(vs_shader, shaders, seen_shaders, shader_usage, eid, draw_name)
            if ps_shader:
                _record_shader(ps_shader, shaders, seen_shaders, shader_usage, eid, draw_name)

        events.append(event)

    pipeline_samples = analysis.get("pipeline_samples") or {}
    samples = None
    if isinstance(pipeline_samples, dict):
        samples = pipeline_samples.get("samples")
    if isinstance(samples, list):
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            event_id = sample.get("event_id") or sample.get("eventId")
            _record_shader_usage(
                shader_usage, sample.get("vertex_shader_id"), event_id
            )
            _record_shader_usage(
                shader_usage, sample.get("pixel_shader_id"), event_id
            )
            _record_shader_usage(
                shader_usage, sample.get("compute_shader_id"), event_id
            )

    return BundleData(
        events=events,
        textures=textures,
        shaders=shaders,
        stats=stats,
        shader_usage=shader_usage,
    )
