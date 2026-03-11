from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class OfflineSnapshotBuilder:
    """Builds offline snapshot.v1 payload from normalized XML/provider data."""

    REQUIRED_TOP_LEVEL_KEYS = (
        "schema_version",
        "meta",
        "preflight",
        "overview",
        "actions",
        "resources",
        "findings",
        "recommendations",
        "availability",
    )

    DEFAULT_MCP_HINT = (
        "Use MCP query to fill unavailable offline fields (timings/pipelines/full shader source)."
    )

    def __init__(self, mcp_hint: str = DEFAULT_MCP_HINT):
        self._mcp_hint = mcp_hint

    def build(
        self,
        *,
        capture_name: str,
        xml_path: str,
        driver: str,
        draw_calls: List[Dict[str, Any]],
        textures: List[Dict[str, Any]],
        buffers: List[Dict[str, Any]],
        shaders: Optional[List[Dict[str, Any]]] = None,
        generated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        shaders = shaders or []
        generated_at = generated_at or datetime.now().astimezone().isoformat()

        actions = self._build_actions(draw_calls)
        textures_payload = self._build_textures(textures)
        buffers_payload = self._build_buffers(buffers)
        shaders_payload = self._build_shaders(shaders)
        findings: List[Dict[str, Any]] = []
        recommendations = self._build_recommendations()

        availability = self._build_availability(
            actions=actions,
            textures=textures_payload,
            shaders=shaders_payload,
        )
        preflight = self._build_preflight(availability)

        snapshot: Dict[str, Any] = {
            "schema_version": "snapshot.v1",
            "meta": {
                "capture_name": capture_name,
                "xml_path": xml_path,
                "driver": driver or "Unknown",
                "source": "offline",
                "generated_at": generated_at,
                "generator": "scripts/rdc_analyzer/xml_to_bundle.py",
                "availability_summary": {
                    "status": availability.get("status", "partial"),
                    "missing_count": len(availability.get("missing_fields", [])),
                },
            },
            "preflight": preflight,
            "overview": self._build_overview(actions, textures_payload, buffers_payload, shaders_payload),
            "timings": {},
            "actions": actions,
            "passes": [],
            "resources": {
                "textures": textures_payload,
                "buffers": buffers_payload,
            },
            "shaders": shaders_payload,
            "pipelines": [],
            "findings": findings,
            "recommendations": recommendations,
            "evidence_index": self._build_evidence_index(actions, textures_payload, shaders_payload),
            "availability": availability,
        }

        for key in self.REQUIRED_TOP_LEVEL_KEYS:
            if key not in snapshot:
                raise ValueError(f"snapshot missing required top-level key: {key}")

        return snapshot

    def _build_actions(self, draw_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for idx, dc in enumerate(draw_calls or []):
            event_id = dc.get("event_id", 0) or idx + 1
            name = dc.get("name", "Unknown")
            action_type = self._detect_action_type(name, bool(dc.get("is_dispatch", False)))
            render_targets = self._normalize_render_targets(dc.get("render_targets", []))
            depth_target = self._normalize_depth_target(dc.get("depth_target"))

            action: Dict[str, Any] = {
                "event_id": str(event_id),
                "name": name,
                "type": action_type,
                "indices": int(dc.get("index_count", 0) or 0),
                "vertices": int(dc.get("vertex_count", 0) or 0),
                "instances": int(dc.get("instance_count", 1) or 1),
                "marker": dc.get("marker", "") or "",
                "render_targets": render_targets,
                "depth_target": depth_target,
                "availability": {
                    "render_targets": "partial",
                    "depth_target": "partial",
                },
            }
            actions.append(action)

        return actions

    def _build_textures(self, textures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for i, tex in enumerate(textures or []):
            resource_id = str(tex.get("resource_id") or tex.get("id") or f"tex-{i}")
            width = int(tex.get("width", 0) or 0)
            height = int(tex.get("height", 0) or 0)
            depth = int(tex.get("depth", 1) or 1)
            array_size = int(tex.get("array_size", tex.get("arrayLayers", 1)) or 1)
            format_name = tex.get("format", "Unknown")
            thumbnail = tex.get("thumbnail", "") or ""

            payload.append(
                {
                    "resource_id": resource_id,
                    "name": tex.get("name", "") or f"Texture_{i}",
                    "type": "texture",
                    "width": width,
                    "height": height,
                    "depth": depth,
                    "array_size": array_size,
                    "format": format_name,
                    "size_bytes": int(tex.get("size_bytes", 0) or 0),
                    "thumbnail": thumbnail,
                    "usage": tex.get("usage", []) or [],
                    "availability": {
                        "thumbnail": "available" if thumbnail else "missing",
                    },
                }
            )

        return payload

    def _build_buffers(self, buffers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for i, buf in enumerate(buffers or []):
            resource_id = str(buf.get("resource_id") or buf.get("id") or f"buf-{i}")
            payload.append(
                {
                    "resource_id": resource_id,
                    "name": buf.get("name", "") or f"Buffer_{i}",
                    "type": "buffer",
                    "size_bytes": int(buf.get("size", 0) or 0),
                    "usage": buf.get("usage", "") or "",
                    "availability": {
                        "metadata": "partial",
                    },
                }
            )
        return payload

    def _build_shaders(self, shaders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for i, shader in enumerate(shaders or []):
            shader_id = str(shader.get("id") or f"shader-{i}")
            source_code = shader.get("source_code") or shader.get("source") or ""
            payload.append(
                {
                    "shader_id": shader_id,
                    "name": shader.get("name", "") or f"Shader_{i}",
                    "stage": shader.get("stage", "") or shader.get("type", "") or "Unknown",
                    "entry_point": shader.get("entry_point", "main"),
                    "source_code": source_code,
                    "encoding": shader.get("encoding", "Unknown"),
                    "resource_id": str(shader.get("resource_id", "") or ""),
                    "availability": {
                        "source_code": "available" if source_code else "missing",
                    },
                }
            )
        return payload

    def _build_overview(
        self,
        actions: List[Dict[str, Any]],
        textures: List[Dict[str, Any]],
        buffers: List[Dict[str, Any]],
        shaders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        draw_calls = sum(1 for a in actions if a.get("type") == "Draw")
        dispatch_calls = sum(1 for a in actions if a.get("type") == "Dispatch")
        clear_calls = sum(1 for a in actions if a.get("type") == "Clear")
        vram_bytes = sum(int(t.get("size_bytes", 0) or 0) for t in textures)

        return {
            "summary": {
                "actions": len(actions),
                "draw_calls": draw_calls,
                "dispatch_calls": dispatch_calls,
                "clear_calls": clear_calls,
                "textures": len(textures),
                "buffers": len(buffers),
                "shaders": len(shaders),
                "vram_bytes_estimate": vram_bytes,
            },
            "top_actions": actions[:10],
            "availability": {
                "status": "partial",
            },
        }

    def _build_recommendations(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "offline-mcp-fill",
                "severity": "info",
                "category": "data-availability",
                "title": "补齐离线缺失字段",
                "description": "离线路径缺少部分 timing/pipeline/完整 shader 信息。",
                "suggestion": self._mcp_hint,
                "verification_plan": {
                    "steps": [
                        "运行 MCP query 获取缺失字段",
                        "对齐 event/resource/shader 证据链后再做归因",
                    ]
                },
                "estimated": False,
                "confidence": "high",
            }
        ]

    def _build_availability(
        self,
        *,
        actions: List[Dict[str, Any]],
        textures: List[Dict[str, Any]],
        shaders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        texture_with_thumbnail = sum(1 for t in textures if t.get("thumbnail"))
        shader_with_source = sum(1 for s in shaders if s.get("source_code"))

        missing_fields = [
            "timings",
            "passes",
            "pipelines",
        ]
        if texture_with_thumbnail == 0 and textures:
            missing_fields.append("resources.textures.thumbnail")
        if shaders and shader_with_source < len(shaders):
            missing_fields.append("shaders.source_code")

        return {
            "source": "offline",
            "status": "partial",
            "missing_fields": missing_fields,
            "mcp_hint": self._mcp_hint,
            "fields": {
                "timings": "missing",
                "passes": "missing",
                "pipelines": "missing",
                "actions": "available" if actions else "partial",
                "resources": "available" if textures else "partial",
                "shaders": "partial" if shaders else "missing",
            },
            "metrics": {
                "textures_with_thumbnail": texture_with_thumbnail,
                "textures_total": len(textures),
                "shaders_with_source": shader_with_source,
                "shaders_total": len(shaders),
            },
        }

    def _build_preflight(self, availability: Dict[str, Any]) -> Dict[str, Any]:
        missing = availability.get("missing_fields", [])
        status = "warning" if missing else "ok"
        missing_data = [{"key": key, "reason": "offline path partial data"} for key in missing]
        return {
            "status": status,
            "missing_data": missing_data,
            "capture_recommendations": [self._mcp_hint] if missing else [],
        }

    def _build_evidence_index(
        self,
        actions: List[Dict[str, Any]],
        textures: List[Dict[str, Any]],
        shaders: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, str]]:
        return {
            "events": {str(a.get("event_id")): f"events.html#event-{a.get('event_id')}" for a in actions},
            "resources": {
                str(t.get("resource_id")): f"textures.html#resource-{t.get('resource_id')}" for t in textures
            },
            "shaders": {str(s.get("shader_id")): f"shaders.html#shader-{s.get('shader_id')}" for s in shaders},
        }

    @staticmethod
    def _detect_action_type(name: str, is_dispatch: bool) -> str:
        lowered = (name or "").lower()
        if is_dispatch or "dispatch" in lowered:
            return "Dispatch"
        if "clear" in lowered:
            return "Clear"
        return "Draw"

    @staticmethod
    def _normalize_render_targets(items: Any) -> List[Dict[str, Any]]:
        targets: List[Dict[str, Any]] = []
        for index, item in enumerate(items or []):
            if isinstance(item, dict):
                resource_id = item.get("id") or item.get("resource_id")
                slot = item.get("slot", index)
            else:
                resource_id = item
                slot = index
            if not resource_id:
                continue
            targets.append({"resource_id": str(resource_id), "slot": int(slot)})
        return targets

    @staticmethod
    def _normalize_depth_target(item: Any) -> Dict[str, Any]:
        if isinstance(item, dict):
            resource_id = item.get("id") or item.get("resource_id")
            aspect = item.get("aspect", "")
        else:
            resource_id = item
            aspect = ""
        if not resource_id:
            return {}
        payload = {"resource_id": str(resource_id)}
        if aspect:
            payload["aspect"] = str(aspect)
        return payload
