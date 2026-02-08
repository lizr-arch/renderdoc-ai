import json
import struct
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_resolve_fbx_backend_prefers_python_binding(monkeypatch):
    try:
        from converters.fbx_sdk_bridge import resolve_fbx_backend
    except ImportError as exc:
        pytest.fail(f"fbx_sdk_bridge missing: {exc}")

    monkeypatch.setitem(sys.modules, "fbx", object())
    assert resolve_fbx_backend() == "python"


def test_resolve_fbx_backend_none_when_missing(monkeypatch):
    try:
        from converters.fbx_sdk_bridge import resolve_fbx_backend
    except ImportError as exc:
        pytest.fail(f"fbx_sdk_bridge missing: {exc}")

    monkeypatch.delitem(sys.modules, "fbx", raising=False)
    assert resolve_fbx_backend() in {"cli", "none"}


def _write_mesh_intermediate(root: Path) -> None:
    mesh_dir = root / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    mesh = {
        "mesh": {
            "vertex_layout": [
                {"semantic": "POSITION", "format": "float3", "offset": 0, "stride": 12}
            ],
            "vertex_count": 3,
            "index_format": "uint16",
            "index_count": 3,
        }
    }
    mesh_dir.joinpath("mesh.json").write_text(
        json.dumps(mesh), encoding="utf-8"
    )

    vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    vertex_bytes = b"".join(struct.pack("<fff", *v) for v in vertices)
    mesh_dir.joinpath("vertex.bin").write_bytes(vertex_bytes)
    mesh_dir.joinpath("index.bin").write_bytes(b"\x00\x00\x01\x00\x02\x00")


def test_cli_creates_stats(tmp_path, monkeypatch):
    try:
        import export_fbx_assets as exporter
    except ImportError as exc:
        pytest.fail(f"export_fbx_assets missing: {exc}")

    intermediate = tmp_path / "intermediate"
    _write_mesh_intermediate(intermediate)
    material_dir = intermediate / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps({"material": {"textures": []}}), encoding="utf-8"
    )

    monkeypatch.setenv("RDC_FBX_ALLOW_MISSING", "1")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert exporter.main(
        [
            "--intermediate",
            str(intermediate),
            "--out",
            str(out_dir),
            "--event",
            "1",
        ]
    ) == 0
    stats_path = out_dir / "event_1" / "stats.json"
    assert stats_path.exists()

    unity_plan = out_dir / "event_1" / "fbx" / "unity" / "shader_import_plan.json"
    unreal_plan = out_dir / "event_1" / "fbx" / "unreal" / "shader_import_plan.json"
    assert unity_plan.exists()
    assert unreal_plan.exists()

    unity_payload = json.loads(unity_plan.read_text(encoding="utf-8"))
    unreal_payload = json.loads(unreal_plan.read_text(encoding="utf-8"))
    assert unity_payload["shader_count"] == 0
    assert unreal_payload["shader_count"] == 0
    assert unity_payload.get("execution", {}).get("status_counts", {}) == {}
    assert unreal_payload.get("execution", {}).get("status_counts", {}) == {}


def test_shader_import_plan_routes_by_source_kind(tmp_path, monkeypatch):
    import export_fbx_assets as exporter

    intermediate = tmp_path / "intermediate"
    _write_mesh_intermediate(intermediate)

    material_dir = intermediate / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_dir.joinpath("material.json").write_text(
        json.dumps({"material": {"textures": []}}), encoding="utf-8"
    )

    shaders_dir = intermediate / "shaders"
    shaders_dir.mkdir(parents=True, exist_ok=True)
    shaders_dir.joinpath("vs.json").write_text(
        json.dumps(
            {
                "shader": {
                    "stage": "vs",
                    "bytecode_format": "spirv",
                    "entry": "main_vs",
                    "source_kind": "vulkan_shader_module",
                    "source_resource_id": 101,
                    "path": "vs.bin",
                }
            }
        ),
        encoding="utf-8",
    )
    shaders_dir.joinpath("ps.json").write_text(
        json.dumps(
            {
                "shader": {
                    "stage": "ps",
                    "bytecode_format": "dxbc",
                    "entry": "main_ps",
                    "source_kind": "d3d11_shader_bytecode",
                    "source_resource_id": 202,
                    "path": "ps.bin",
                }
            }
        ),
        encoding="utf-8",
    )
    shaders_dir.joinpath("vs.bin").write_bytes(b"SPIRV")
    shaders_dir.joinpath("ps.bin").write_bytes(b"DXBC")

    monkeypatch.setenv("RDC_FBX_ALLOW_MISSING", "1")
    monkeypatch.setattr(exporter, "resolve_spirv_cross_path", lambda cli: cli or "mock_spirv_cross")
    monkeypatch.setattr(
        exporter,
        "run_spirv_cross",
        lambda path, data: "// converted by mock spirv-cross\nfloat4 main() : SV_Target { return 1; }\n",
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    assert exporter.main(
        [
            "--intermediate",
            str(intermediate),
            "--out",
            str(out_dir),
            "--event",
            "9",
            "--spirv-cross",
            "mock_spirv_cross",
        ]
    ) == 0

    unity_plan_path = out_dir / "event_9" / "fbx" / "unity" / "shader_import_plan.json"
    unreal_plan_path = out_dir / "event_9" / "fbx" / "unreal" / "shader_import_plan.json"

    unity_plan = json.loads(unity_plan_path.read_text(encoding="utf-8"))
    unreal_plan = json.loads(unreal_plan_path.read_text(encoding="utf-8"))

    assert unity_plan["shader_count"] == 2
    assert unreal_plan["shader_count"] == 2

    unity_by_stage = {item["stage"]: item for item in unity_plan["shaders"]}
    unreal_by_stage = {item["stage"]: item for item in unreal_plan["shaders"]}

    assert unity_by_stage["vs"]["strategy"] == "spirv_to_hlsl"
    assert unity_by_stage["vs"]["tool"] == "spirv-cross"
    assert unity_by_stage["vs"]["output_source"].endswith("vs.hlsl")

    assert unity_by_stage["ps"]["strategy"] == "dxbc_to_hlsl"
    assert unity_by_stage["ps"]["tool"] == "dxbc-toolchain"
    assert unity_by_stage["ps"]["output_source"].endswith("ps.hlsl")

    assert unreal_by_stage["vs"]["strategy"] == "spirv_to_hlsl"
    assert unreal_by_stage["vs"]["output_source"].endswith("vs.usf")

    assert unreal_by_stage["ps"]["strategy"] == "dxbc_to_hlsl"
    assert unreal_by_stage["ps"]["output_source"].endswith("ps.usf")

    assert unity_by_stage["vs"]["status"] == "converted"
    assert unity_by_stage["ps"]["status"] == "stubbed_dxbc"
    assert unreal_by_stage["vs"]["status"] == "converted"
    assert unreal_by_stage["ps"]["status"] == "stubbed_dxbc"

    unity_vs = unity_plan_path.parent / unity_by_stage["vs"]["generated_file"]
    unity_ps = unity_plan_path.parent / unity_by_stage["ps"]["generated_file"]
    unreal_vs = unreal_plan_path.parent / unreal_by_stage["vs"]["generated_file"]
    unreal_ps = unreal_plan_path.parent / unreal_by_stage["ps"]["generated_file"]

    assert unity_vs.exists()
    assert unity_ps.exists()
    assert unreal_vs.exists()
    assert unreal_ps.exists()

    assert "converted by mock spirv-cross" in unity_vs.read_text(encoding="utf-8")
    assert "dxbc conversion adapter placeholder" in unity_ps.read_text(encoding="utf-8")
    assert "converted by mock spirv-cross" in unreal_vs.read_text(encoding="utf-8")
    assert "dxbc conversion adapter placeholder" in unreal_ps.read_text(encoding="utf-8")
