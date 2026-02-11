import json
import re
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from report_bundle_generator import ReportBundleGenerator  # noqa: E402


def _extract_embedded_json(html: str, candidates):
    for name in candidates:
        match = re.search(rf"(?:const|let)\s+{name}\s*=\s*", html)
        if not match:
            continue

        idx = match.end()
        while idx < len(html) and html[idx].isspace():
            idx += 1

        if idx >= len(html) or html[idx] not in "[{":
            continue

        opening = html[idx]
        closing = "]" if opening == "[" else "}"
        depth = 1
        pos = idx + 1
        in_string = None
        escaping = False

        while pos < len(html) and depth > 0:
            ch = html[pos]
            if in_string:
                if escaping:
                    escaping = False
                elif ch == "\\":
                    escaping = True
                elif ch == in_string:
                    in_string = None
            else:
                if ch in ('"', "'"):
                    in_string = ch
                elif ch == opening:
                    depth += 1
                elif ch == closing:
                    depth -= 1
            pos += 1

        if depth != 0:
            continue

        return json.loads(html[idx:pos])

    raise AssertionError(f"missing embedded json: {candidates}")


def test_report_schema_files_exist():
    schema_dir = SCRIPT_DIR / "schema"
    assert (schema_dir / "report_heatmap_data.schema.json").exists()
    assert (schema_dir / "shader_data.schema.json").exists()


def test_generate_shaders_validates_schema(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")

    gen.set_shaders(
        shaders=[
            {
                "id": "shader_001",
                "name": "MainPS",
                "type": "fragment",
                "source_hlsl": "float4 main() : SV_Target { return 0; }",
            }
        ],
        mali_data={
            "shader_001": {
                "cycles": {
                    "total": 10.0,
                    "arithmetic": 5.0,
                    "load_store": 2.0,
                    "texture": 3.0,
                    "varying": 1.0,
                },
                "bound": "T",
                "work_registers": 20,
                "uniform_registers": 8,
                "stack_spilling": False,
                "has_late_zs": False,
            }
        },
        usage_map={
            "shader_001": [
                {"event_id": 1, "draw_name": "DrawMesh", "slot": 0},
            ]
        },
    )

    html = gen.generate_shaders()
    shader_data = _extract_embedded_json(html, ["embeddedData", "shaderData"])
    assert shader_data and shader_data[0]["dynamicMetrics"]["drawCount"] == 1


def test_generate_events_validates_heatmap_schema(tmp_path):
    gen = ReportBundleGenerator(output_dir=tmp_path, capture_name="t.rdc")

    gen.set_textures(
        textures=[
            {
                "id": "tex_001",
                "name": "T",
                "width": 1,
                "height": 1,
                "format": "VK_FORMAT_R8G8B8A8_UNORM",
            }
        ],
        usage_map={},
    )

    gen.set_shaders(
        shaders=[
            {
                "id": "shader_001",
                "name": "S",
                "type": "fragment",
            }
        ],
        mali_data={},
        usage_map={},
    )

    # events 必须含 textures/shaders 字段，否则 heatmap 会为空但仍应符合 schema
    gen.set_events(
        events=[
            {
                "eventId": 1,
                "eid": 1,
                "name": "Draw",
                "type": "Draw",
                "textures": [{"id": "tex_001", "slot": 0}],
                "shaders": [{"id": "shader_001", "slot": 0}],
            }
        ]
    )

    html = gen.generate_events()
    heatmap = _extract_embedded_json(html, ["embeddedHeatmap", "heatmapData"])
    assert isinstance(heatmap, dict)
    assert "textures" in heatmap and "shaders" in heatmap
