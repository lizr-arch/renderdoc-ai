from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


SNAPSHOT_SCHEMA_VERSION = "snapshot.v1"

_STAGE_TO_TYPE = {
    "vertex": "VS",
    "vs": "VS",
    "vert": "VS",
    "pixel": "PS",
    "ps": "PS",
    "fragment": "PS",
    "frag": "PS",
    "fs": "PS",
    "compute": "CS",
    "cs": "CS",
    "geometry": "GS",
    "gs": "GS",
    "hull": "HS",
    "hs": "HS",
    "domain": "DS",
    "ds": "DS",
}


def is_snapshot_v1_payload(data: Any) -> bool:
    return isinstance(data, dict) and data.get("schema_version") == SNAPSHOT_SCHEMA_VERSION


def snapshot_to_capture_data(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    meta = snapshot.get("meta", {}) or {}
    overview = snapshot.get("overview", {}) or {}
    summary = overview.get("summary", {}) or {}
    availability = snapshot.get("availability", {}) or {}
    actions = snapshot.get("actions", []) or []
    resources = snapshot.get("resources", {}) or {}
    textures = resources.get("textures", []) or []
    buffers = resources.get("buffers", []) or []
    shaders = snapshot.get("shaders", []) or []
    passes = snapshot.get("passes", []) or []
    pipelines = snapshot.get("pipelines", []) or []
    findings = snapshot.get("findings", []) or []
    recommendations = snapshot.get("recommendations", []) or []
    evidence_index = snapshot.get("evidence_index", {}) or {}

    pipeline_by_id = _index_pipelines_by_id(pipelines)
    pipeline_by_event = _index_pipelines_by_event(pipelines)

    events = [
        _normalize_action(action, index, pipeline_by_id, pipeline_by_event)
        for index, action in enumerate(actions)
    ]
    normalized_textures = [_normalize_texture(texture, index) for index, texture in enumerate(textures)]
    normalized_buffers = [_normalize_buffer(buffer_obj, index) for index, buffer_obj in enumerate(buffers)]
    normalized_shaders = [_normalize_shader(shader, index) for index, shader in enumerate(shaders)]

    counts = _build_snapshot_counts(
        summary=summary,
        events=events,
        textures=normalized_textures,
        buffers=normalized_buffers,
        shaders=normalized_shaders,
        passes=passes,
        pipelines=pipelines,
        findings=findings,
        recommendations=recommendations,
    )

    api_type = (
        meta.get("graphics_api")
        or meta.get("driver")
        or meta.get("api")
        or "Unknown"
    )

    return {
        "apiType": api_type,
        "statistics": {
            "totalDrawCalls": counts["draw_calls"],
            "dispatchCalls": counts["dispatch_calls"],
            "totalTriangles": counts["triangles"],
            "totalVertices": counts["vertices"],
            "textureCount": counts["textures"],
            "bufferCount": counts["buffers"],
            "shaderCount": counts["shaders"],
            "passCount": counts["passes"],
            "pipelineCount": counts["pipelines"],
            "findingCount": counts["findings"],
            "recommendationCount": counts["recommendations"],
            "shaderChanges": _to_int(summary.get("shader_changes"), 0),
            "renderTargetSwitches": _to_int(summary.get("render_target_switches"), 0),
        },
        "events": events,
        "textures": normalized_textures,
        "buffers": normalized_buffers,
        "shaders": normalized_shaders,
        "_source_schema": SNAPSHOT_SCHEMA_VERSION,
        "_snapshot_meta": {
            "capture_name": meta.get("capture_name", ""),
            "source": meta.get("source", ""),
            "generated_at": meta.get("generated_at", ""),
            "report_surface": meta.get("report_surface", ""),
            "api_type": api_type,
        },
        "_snapshot_counts": counts,
        "_snapshot_availability": {
            "status": availability.get("status", "unknown"),
            "missing_fields": list(availability.get("missing_fields", []) or []),
            "fields": dict(availability.get("fields", {}) or {}),
        },
        "_snapshot_evidence_index": evidence_index,
    }


def _build_snapshot_counts(
    *,
    summary: Dict[str, Any],
    events: List[Dict[str, Any]],
    textures: List[Dict[str, Any]],
    buffers: List[Dict[str, Any]],
    shaders: List[Dict[str, Any]],
    passes: List[Dict[str, Any]],
    pipelines: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
) -> Dict[str, int]:
    draw_calls = _summary_int(summary, ("draw_call_count", "draw_calls"), 0)
    if draw_calls == 0:
        draw_calls = sum(1 for event in events if _is_draw_event(event))

    dispatch_calls = _summary_int(summary, ("dispatch_count", "dispatch_calls"), 0)
    if dispatch_calls == 0:
        dispatch_calls = sum(1 for event in events if _is_dispatch_event(event))

    triangles = _summary_int(summary, ("total_triangles", "triangles"), 0)
    if triangles == 0:
        triangles = sum(_event_triangle_count(event) for event in events if _is_draw_event(event))

    vertices = _summary_int(summary, ("total_vertices", "vertices"), 0)
    if vertices == 0:
        vertices = sum(_event_vertex_count(event) for event in events if _is_draw_event(event))

    actions_count = _summary_int(summary, ("action_count", "actions"), len(events))

    return {
        "actions": actions_count if actions_count > 0 else len(events),
        "draw_calls": draw_calls,
        "dispatch_calls": dispatch_calls,
        "triangles": triangles,
        "vertices": vertices,
        "textures": _summary_int(summary, ("texture_count", "textures"), len(textures)),
        "buffers": _summary_int(summary, ("buffer_count", "buffers"), len(buffers)),
        "shaders": _summary_int(summary, ("shader_count", "shaders"), len(shaders)),
        "passes": _summary_int(summary, ("pass_count", "passes"), len(passes)),
        "pipelines": _summary_int(summary, ("pipeline_count", "pipelines"), len(pipelines)),
        "findings": _summary_int(summary, ("finding_count", "findings"), len(findings)),
        "recommendations": _summary_int(
            summary, ("recommendation_count", "recommendations"), len(recommendations)
        ),
    }


def _normalize_action(
    action: Dict[str, Any],
    index: int,
    pipeline_by_id: Dict[str, Dict[str, Any]],
    pipeline_by_event: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    event_id = _to_int(action.get("event_id"), index + 1)
    action_kind = _normalize_action_kind(action)
    name = str(action.get("name") or action_kind.capitalize())
    index_count = _first_int(action, ("indexCount", "index_count", "indices"), 0)
    vertex_count = _first_int(action, ("vertexCount", "vertex_count", "vertices"), 0)
    instance_count = _first_int(action, ("instanceCount", "instance_count", "instances"), 1)
    marker_path = _normalize_marker_path(action.get("marker_path"), action.get("marker"))
    pipeline_state = _build_pipeline_state(
        action=action,
        event_id=event_id,
        pipeline_by_id=pipeline_by_id,
        pipeline_by_event=pipeline_by_event,
    )

    return {
        "eventId": event_id,
        "name": name,
        "indexCount": index_count,
        "vertexCount": vertex_count,
        "instanceCount": instance_count,
        "markerPath": marker_path,
        "marker_path": marker_path,
        "pipelineState": pipeline_state,
        "actionKind": action_kind,
    }


def _normalize_texture(texture: Dict[str, Any], index: int) -> Dict[str, Any]:
    width = _first_int(texture, ("width",), 0)
    height = _first_int(texture, ("height",), 0)
    depth = _first_int(texture, ("depth",), 1)
    array_size = _first_int(texture, ("arraySize", "array_size"), 1)
    mip_levels = _first_int(texture, ("mipLevels", "mip_count", "mips"), 1)
    format_name = str(texture.get("format", "") or "Unknown")
    memory_size = _first_int(texture, ("memorySize", "size_bytes"), 0)
    if memory_size <= 0:
        memory_size = _estimate_texture_memory(width, height, depth, array_size, mip_levels, format_name)

    return {
        "resourceId": str(
            texture.get("resourceId")
            or texture.get("resource_id")
            or texture.get("id")
            or f"texture-{index}"
        ),
        "name": str(texture.get("name", "") or f"Texture_{index}"),
        "width": width,
        "height": height,
        "depth": depth,
        "arraySize": array_size,
        "mipLevels": mip_levels,
        "format": format_name,
        "memorySize": memory_size,
        "usage": list(texture.get("usage_tags", texture.get("usage", [])) or []),
    }


def _normalize_buffer(buffer_obj: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "resourceId": str(
            buffer_obj.get("resourceId")
            or buffer_obj.get("resource_id")
            or buffer_obj.get("id")
            or f"buffer-{index}"
        ),
        "name": str(buffer_obj.get("name", "") or f"Buffer_{index}"),
        "size": _first_int(buffer_obj, ("size", "size_bytes", "byte_size", "length"), 0),
        "usage": str(buffer_obj.get("usage", "") or ""),
    }


def _normalize_shader(shader: Dict[str, Any], index: int) -> Dict[str, Any]:
    shader_id = str(shader.get("resourceId") or shader.get("resource_id") or shader.get("shader_id") or shader.get("id") or f"shader-{index}")
    shader_type = _normalize_shader_type(shader.get("stage") or shader.get("type"))
    entry_point = str(shader.get("entry_point", "") or "main")
    encoding = str(shader.get("encoding", "") or "unknown")
    hash_value = str(shader.get("hash", "") or "").strip()
    if not hash_value:
        hash_value = _build_shader_hash(shader, shader_id, shader_type, entry_point, encoding)

    return {
        "resourceId": shader_id,
        "name": str(shader.get("name", "") or shader_id),
        "type": shader_type,
        "hash": hash_value,
        "entry_point": entry_point,
        "encoding": encoding,
    }


def _build_pipeline_state(
    *,
    action: Dict[str, Any],
    event_id: int,
    pipeline_by_id: Dict[str, Dict[str, Any]],
    pipeline_by_event: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    pipeline_ref = action.get("pipeline_ref") or action.get("pipeline_id")
    pipeline = None
    if pipeline_ref is not None:
        pipeline = pipeline_by_id.get(str(pipeline_ref))
    if pipeline is None:
        pipeline = pipeline_by_event.get(event_id)
    if not pipeline:
        return {}

    pipeline_state: Dict[str, Any] = {}

    shader_refs: Dict[str, Dict[str, str]] = {}
    for field_name, shader_stage in (
        ("vs_ref", "VS"),
        ("ps_ref", "PS"),
        ("cs_ref", "CS"),
        ("gs_ref", "GS"),
        ("hs_ref", "HS"),
        ("ds_ref", "DS"),
    ):
        shader_id = _extract_shader_ref_id(pipeline.get(field_name))
        if shader_id:
            shader_refs[shader_stage] = {"resourceId": shader_id}
    if shader_refs:
        pipeline_state["shaders"] = shader_refs

    blend_targets = _normalize_blend_targets(pipeline.get("blend", {}))
    if blend_targets:
        pipeline_state["colorBlend"] = {"attachments": blend_targets}
        pipeline_state.setdefault("outputMerger", {})["blendState"] = {"renderTargets": blend_targets}

    depth_stencil = _normalize_depth_stencil(pipeline.get("depth_stencil", pipeline.get("depthStencil", {})))
    if depth_stencil:
        pipeline_state["depthStencil"] = depth_stencil
        pipeline_state.setdefault("outputMerger", {})["depthStencilState"] = {
            "depthEnable": depth_stencil.get("depthTestEnable", True)
        }

    return pipeline_state


def _index_pipelines_by_id(pipelines: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for pipeline in pipelines or []:
        pipeline_id = pipeline.get("pipeline_id")
        if pipeline_id is not None:
            result[str(pipeline_id)] = pipeline
    return result


def _index_pipelines_by_event(pipelines: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for pipeline in pipelines or []:
        event_id = _to_int(pipeline.get("event_id"), 0)
        if event_id:
            result[event_id] = pipeline
    return result


def _normalize_action_kind(action: Dict[str, Any]) -> str:
    raw_kind = str(action.get("kind") or action.get("type") or "").strip().lower()
    if raw_kind in ("draw", "drawcall"):
        return "draw"
    if raw_kind == "dispatch":
        return "dispatch"
    if raw_kind == "clear":
        return "clear"
    name = str(action.get("name", "") or "").lower()
    if "dispatch" in name:
        return "dispatch"
    if "clear" in name:
        return "clear"
    return "draw"


def _normalize_marker_path(marker_path: Any, marker: Any) -> str:
    value = marker_path if marker_path not in (None, "") else marker
    if isinstance(value, list):
        return "/".join(str(item) for item in value if item not in (None, ""))
    if value is None:
        return ""
    return str(value)


def _normalize_shader_type(stage: Any) -> str:
    if stage is None:
        return "Unknown"
    text = str(stage).strip()
    if not text:
        return "Unknown"
    normalized = _STAGE_TO_TYPE.get(text.lower())
    return normalized or text.upper()


def _extract_shader_ref_id(shader_ref: Any) -> str:
    if isinstance(shader_ref, dict):
        value = shader_ref.get("id") or shader_ref.get("resource_id") or shader_ref.get("shader_id")
        if value is not None:
            return str(value)
    elif shader_ref not in (None, ""):
        return str(shader_ref)
    return ""


def _normalize_blend_targets(blend: Any) -> List[Dict[str, Any]]:
    if not isinstance(blend, dict) or not blend:
        return []
    attachments = blend.get("attachments") or blend.get("targets") or []
    result: List[Dict[str, Any]] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        if "blendEnable" in attachment:
            result.append({"blendEnable": bool(attachment.get("blendEnable", False))})
        elif "enabled" in attachment:
            result.append({"blendEnable": bool(attachment.get("enabled", False))})
    if not result and ("blendEnable" in blend or "enabled" in blend):
        result.append({"blendEnable": bool(blend.get("blendEnable", blend.get("enabled", False)))})
    return result


def _normalize_depth_stencil(depth_stencil: Any) -> Dict[str, Any]:
    if not isinstance(depth_stencil, dict) or not depth_stencil:
        return {}
    if "depthTestEnable" in depth_stencil:
        return {"depthTestEnable": bool(depth_stencil.get("depthTestEnable", True))}
    if "depthEnable" in depth_stencil:
        return {"depthTestEnable": bool(depth_stencil.get("depthEnable", True))}
    return {}


def _build_shader_hash(
    shader: Dict[str, Any],
    shader_id: str,
    shader_type: str,
    entry_point: str,
    encoding: str,
) -> str:
    source_payload = (
        shader.get("source_high_level")
        or shader.get("source_asm")
        or shader.get("source_code")
        or shader.get("source")
        or ""
    )
    if isinstance(source_payload, (dict, list)):
        source_text = json.dumps(source_payload, sort_keys=True, ensure_ascii=False)
    else:
        source_text = str(source_payload)

    if not source_text:
        source_text = shader_id

    hash_input = "|".join((shader_type, entry_point, encoding, source_text))
    return hashlib.sha1(hash_input.encode("utf-8")).hexdigest()


def _estimate_texture_memory(
    width: int,
    height: int,
    depth: int,
    array_size: int,
    mip_levels: int,
    format_name: str,
) -> int:
    if width <= 0 or height <= 0:
        return 0
    bytes_per_pixel = _estimate_bytes_per_pixel(format_name)
    base_size = width * height * max(depth, 1) * bytes_per_pixel
    if mip_levels > 1:
        base_size = int(base_size * 1.33)
    return int(base_size * max(array_size, 1))


def _estimate_bytes_per_pixel(format_name: str) -> float:
    fmt = str(format_name or "").upper()
    if "BC1" in fmt or "DXT1" in fmt:
        return 0.5
    if "BC2" in fmt or "BC3" in fmt or "DXT3" in fmt or "DXT5" in fmt:
        return 1.0
    if "BC4" in fmt:
        return 0.5
    if "BC5" in fmt:
        return 1.0
    if "BC6" in fmt or "BC7" in fmt:
        return 1.0
    if "ASTC" in fmt:
        return 1.0
    if "ETC" in fmt or "EAC" in fmt:
        return 0.5
    if "R32G32B32A32" in fmt:
        return 16.0
    if "R32G32B32" in fmt:
        return 12.0
    if "R32G32" in fmt:
        return 8.0
    if "R32" in fmt:
        return 4.0
    if "R16G16B16A16" in fmt:
        return 8.0
    if "R16G16B16" in fmt:
        return 6.0
    if "R16G16" in fmt:
        return 4.0
    if "R16" in fmt:
        return 2.0
    if "R8G8B8A8" in fmt or "B8G8R8A8" in fmt:
        return 4.0
    if "R8G8B8" in fmt or "B8G8R8" in fmt:
        return 3.0
    if "R8G8" in fmt:
        return 2.0
    if "R8" in fmt or "A8" in fmt:
        return 1.0
    if "D32" in fmt or "R10G10B10A2" in fmt or "R11G11B10" in fmt:
        return 4.0
    if "D24" in fmt:
        return 4.0
    if "D16" in fmt:
        return 2.0
    if "S8" in fmt:
        return 1.0
    return 4.0


def _summary_int(summary: Dict[str, Any], keys: tuple[str, ...], default: int) -> int:
    for key in keys:
        if key in summary:
            return _to_int(summary.get(key), default)
    return default


def _first_int(payload: Dict[str, Any], keys: tuple[str, ...], default: int) -> int:
    for key in keys:
        if key in payload:
            return _to_int(payload.get(key), default)
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_draw_event(event: Dict[str, Any]) -> bool:
    return str(event.get("actionKind", "")).lower() == "draw"


def _is_dispatch_event(event: Dict[str, Any]) -> bool:
    return str(event.get("actionKind", "")).lower() == "dispatch"


def _event_vertex_count(event: Dict[str, Any]) -> int:
    count = max(_to_int(event.get("indexCount"), 0), _to_int(event.get("vertexCount"), 0))
    return count * max(_to_int(event.get("instanceCount"), 1), 1)


def _event_triangle_count(event: Dict[str, Any]) -> int:
    return _event_vertex_count(event) // 3
