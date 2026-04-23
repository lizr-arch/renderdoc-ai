import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.snapshot_template_renderer import SnapshotTemplateRenderer


def test_snapshot_renderer_outputs_minimum_pages(tmp_path: Path):
    snapshot = {
        "schema_version": "snapshot.v1",
        "meta": {
            "capture_name": "demo",
            "source": "offline",
            "generated_at": "2026-03-11T19:30:00+08:00",
        },
        "preflight": {"status": "warning", "missing_data": []},
        "overview": {"summary": {"actions": 1, "textures": 1, "shaders": 1}},
        "actions": [
            {
                "event_id": "101",
                "name": "vkCmdDrawIndexed",
                "type": "Draw",
                "vertices": 24,
                "indices": 36,
                "instances": 1,
            }
        ],
        "resources": {
            "textures": [
                {
                    "resource_id": "176441",
                    "name": "MainColor",
                    "width": 1920,
                    "height": 1080,
                    "format": "R8G8B8A8_UNORM",
                    "size_bytes": 8294400,
                    "thumbnail": "",
                }
            ],
            "buffers": [],
        },
        "shaders": [
            {
                "shader_id": "shader-1",
                "name": "VS_Main",
                "stage": "Vertex",
                "source_code": "void main() {}",
            }
        ],
        "pipelines": [
            {
                "pipeline_id": "pipe-101",
                "event_id": 101,
                "graphics_api": "Vulkan",
                "vs_ref": {"shader_id": "shader-1", "label": "VS_Main"},
                "render_target_refs": [{"resource_id": "176441", "label": "MainColor"}],
                "blend": {"enabled": False},
                "rasterizer": {"cull_mode": "Back"},
                "availability": {"vs_ref": "available", "ps_ref": "missing"},
            }
        ],
        "findings": [],
        "recommendations": [
            {
                "id": "offline-mcp-fill",
                "severity": "info",
                "title": "补齐离线缺失字段",
                "description": "offline partial data",
                "suggestion": "Use MCP query to fill unavailable fields.",
            }
        ],
        "availability": {
            "status": "partial",
            "mcp_hint": "Use MCP query",
            "fields": {
                "actions": "available",
                "resources": "available",
                "shaders": "available",
                "pipelines": "partial",
            },
        },
    }

    renderer = SnapshotTemplateRenderer(tmp_path, capture_name="demo")
    outputs = renderer.render(snapshot)

    expected = {
        "index",
        "events",
        "textures",
        "shaders",
        "pipelines",
        "manifest",
    }
    assert expected.issubset(outputs.keys())

    for page in ["index.html", "events.html", "textures.html", "shaders.html", "pipelines.html"]:
        assert (tmp_path / page).exists()
    assert (tmp_path / "manifest.json").exists()

    events_html = (tmp_path / "events.html").read_text(encoding="utf-8")
    textures_html = (tmp_path / "textures.html").read_text(encoding="utf-8")
    shaders_html = (tmp_path / "shaders.html").read_text(encoding="utf-8")
    pipelines_html = (tmp_path / "pipelines.html").read_text(encoding="utf-8")
    assert 'id="event-101"' in events_html
    assert 'id="resource-176441"' in textures_html
    assert 'id="shader-shader-1"' in shaders_html
    assert 'id="pipeline-pipe-101"' in pipelines_html
    assert 'href="events.html#event-101"' in pipelines_html
    assert "Pipelines (Partial)" in pipelines_html

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "template.v1"
    assert manifest["snapshot_version"] == "snapshot.v1"
    assert manifest["pages"] == ["index", "events", "textures", "shaders", "pipelines"]
