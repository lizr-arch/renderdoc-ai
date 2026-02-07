import json
import re
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from report_bundle_generator import ReportBundleGenerator  # noqa: E402


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
                "cycles": {"total": 10.0, "arithmetic": 5.0, "load_store": 2.0, "texture": 3.0, "varying": 1.0},
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
    match = re.search(r"const shaderData = (\[.*?\]);", html, re.DOTALL)
    assert match

    shader_data = json.loads(match.group(1))
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
    assert "const heatmapData" in html
