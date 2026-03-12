import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from export_messiah_from_bundle import export_messiah_from_bundle, main  # noqa: E402


def _write_bundle(tmp_path: Path, event_id: int = 2001):
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
                                "slot": "PS.t0",
                                "sampler": "PS.s0",
                                "texture_id": 11,
                                "source_path": "textures/tex_11.bin",
                                "output_path": "textures/tex_11.png",
                                "status": "copied_image",
                                "width": 2,
                                "height": 2,
                                "format": "R8G8B8A8",
                            },
                            {
                                "slot": "PS.normal",
                                "sampler": "PS.s1",
                                "texture_id": 12,
                                "source_path": "textures/tex_12.bin",
                                "output_path": "textures/tex_12.bin",
                                "status": "raw_rgba",
                                "width": 2,
                                "height": 2,
                                "format": "R8G8B8A8",
                            },
                            {
                                "slot": "PS.emissive",
                                "sampler": "PS.s2",
                                "texture_id": 13,
                                "source_path": "textures/tex_13.bin",
                                "output_path": "textures/tex_13.png",
                                "status": "copied_image",
                                "width": 2,
                                "height": 2,
                                "format": "R8G8B8A8",
                            },
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
                "shaders": [{"stage": "vs"}, {"stage": "ps"}],
            }
        ),
        encoding="utf-8",
    )

    textures_dir.joinpath("tex_11.png").write_bytes(b"PNGDATA")
    textures_dir.joinpath("tex_12.bin").write_bytes(bytes([128, 64, 32, 255]) * 4)
    return event_root, bundle_root


def test_export_messiah_from_bundle_generates_repository(tmp_path):
    _, bundle_root = _write_bundle(tmp_path, 2101)
    out_root = tmp_path / "out"

    repo_root = export_messiah_from_bundle(bundle_root, out_root)

    assert repo_root.exists()
    assert (repo_root / "resource.repository").exists()

    mesh_files = list((repo_root / "Mesh").glob("**/resource.xml"))
    material_files = list((repo_root / "Material").glob("**/resource.xml"))
    model_files = list((repo_root / "Model").glob("**/resource.xml"))
    texture_files = list((repo_root / "Texture").glob("**/texture.xml"))

    assert mesh_files
    assert material_files
    assert model_files
    assert len(texture_files) == 2

    material_xml = material_files[0].read_text(encoding="utf-8")
    assert "<ShaderName>PBR</ShaderName>" in material_xml
    assert "<Name>tBaseMap</Name>" in material_xml
    assert "<Name>tNormalMap</Name>" in material_xml

    mapping_path = repo_root / "import_bundle_mapping.json"
    assert mapping_path.exists()
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert mapping["material_template"] == "pbr"
    assert mapping["textures"]["count_exported"] == 2
    assert mapping["textures"]["count_missing"] == 1
    assert mapping["textures"]["missing"][0]["parameter"] == "tEmissiveMap"


def test_main_supports_event_root_input(tmp_path):
    event_root, _ = _write_bundle(tmp_path, 2102)
    out_root = tmp_path / "out2"

    rc = main(["--bundle", str(event_root), "--out", str(out_root)])
    assert rc == 0

    repo_root = out_root / "messiah" / "Package" / "Repository" / "rdc_event_2102.local"
    assert repo_root.exists()
    assert (repo_root / "resource.repository").exists()
