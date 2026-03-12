import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR / "exporters"))

from messiah_bundle_adapter import (  # noqa: E402
    collect_material_textures,
    collect_shader_stages,
    detect_event_id,
    infer_material_template,
    load_bundle_payload,
    map_texture_slot_to_parameter,
    parse_obj_mesh,
    resolve_bundle_root,
    resolve_texture_source,
)


def _write_bundle(tmp_path: Path, event_id: int = 1001):
    event_root = tmp_path / f"event_{event_id}"
    bundle_root = event_root / "import_bundle"
    mesh_dir = bundle_root / "mesh"
    materials_dir = bundle_root / "materials"
    textures_dir = bundle_root / "textures"

    mesh_dir.mkdir(parents=True, exist_ok=True)
    materials_dir.mkdir(parents=True, exist_ok=True)
    textures_dir.mkdir(parents=True, exist_ok=True)

    mesh_dir.joinpath("mesh.obj").write_text(
        "\n".join(
            [
                "v 0.0 0.0 0.0",
                "v 1.0 0.0 0.0",
                "v 0.0 1.0 0.0",
                "vt 0.0 0.0",
                "vt 1.0 0.0",
                "vt 0.0 1.0",
                "vn 0.0 0.0 1.0",
                "f 1/1/1 2/2/1 3/3/1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    materials_dir.joinpath("materials.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "event_id": event_id,
                "materials": [
                    {
                        "name": "mat0",
                        "shader": "ps",
                        "textures": [
                            {
                                "slot": "set0.binding0",
                                "sampler": "set0.binding1",
                                "texture_id": 7,
                                "source_path": "textures/tex_7.bin",
                                "output_path": "textures/tex_7.png",
                                "status": "copied_image",
                                "width": 4,
                                "height": 4,
                                "format": "R8G8B8A8",
                            }
                        ],
                        "constants": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle_root.joinpath("bundle_manifest.json").write_text(
        json.dumps(
            {
                "event_id": event_id,
                "api": "Vulkan",
                "shaders": [{"stage": "ps"}],
            }
        ),
        encoding="utf-8",
    )

    textures_dir.joinpath("tex_7.png").write_bytes(b"PNGDATA")
    return event_root, bundle_root


def test_resolve_bundle_root(tmp_path):
    event_root, bundle_root = _write_bundle(tmp_path, 3001)
    assert resolve_bundle_root(bundle_root) == bundle_root
    assert resolve_bundle_root(event_root) == bundle_root


def test_detect_event_id_from_manifest_and_parent(tmp_path):
    _, bundle_root = _write_bundle(tmp_path, 3002)
    manifest, _ = load_bundle_payload(bundle_root)
    assert detect_event_id(bundle_root, manifest=manifest) == 3002
    assert detect_event_id(bundle_root, explicit_event_id=9999, manifest=manifest) == 9999


def test_collect_and_resolve_texture_source(tmp_path):
    _, bundle_root = _write_bundle(tmp_path, 3003)
    _, materials = load_bundle_payload(bundle_root)
    textures = collect_material_textures(materials)
    assert len(textures) == 1
    source = resolve_texture_source(bundle_root, textures[0])
    assert source is not None
    assert source.name == "tex_7.png"


def test_collect_shader_stages(tmp_path):
    _, bundle_root = _write_bundle(tmp_path, 30035)
    manifest, materials = load_bundle_payload(bundle_root)
    stages = collect_shader_stages(manifest, materials)
    assert stages == ["ps"]


def test_infer_material_template_prefers_pbr_tokens(tmp_path):
    _, bundle_root = _write_bundle(tmp_path, 30036)
    manifest, materials = load_bundle_payload(bundle_root)
    materials["materials"][0]["textures"].append(
        {
            "slot": "PS.normal",
            "texture_id": 8,
            "source_path": "textures/tex_8.bin",
            "output_path": "textures/tex_8.png",
        }
    )

    assert infer_material_template(manifest, materials, fallback="unlit") == "pbr"


def test_map_texture_slot_to_parameter_rules():
    assert map_texture_slot_to_parameter({"slot": "PS.t0"}, 0) == "tBaseMap"
    assert map_texture_slot_to_parameter({"slot": "PS.normal"}, 1) == "tNormalMap"
    assert map_texture_slot_to_parameter({"slot": "PS.metallicRoughness"}, 2) == "tPBRMap"
    assert map_texture_slot_to_parameter({"slot": "PS.emissive"}, 3) == "tEmissiveMap"
    assert map_texture_slot_to_parameter({"slot": "PS.custom"}, 4) == "tExtraMap4"


def test_parse_obj_mesh(tmp_path):
    _, bundle_root = _write_bundle(tmp_path, 3004)
    mesh_info = parse_obj_mesh(bundle_root / "mesh" / "mesh.obj")
    assert mesh_info["vertex_count"] == 3
    assert mesh_info["index_count"] == 3
    assert mesh_info["index_format"] == "uint16"
    assert len(mesh_info["vertex_bytes"]) == 3 * 24
    assert len(mesh_info["index_bytes"]) == 3 * 2
