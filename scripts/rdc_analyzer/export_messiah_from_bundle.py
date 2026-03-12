import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))

from engine_guid import hash_guid
from messiah_bundle_adapter import (
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
from messiah_exporter import (
    _build_mesh_xml,
    _build_model_xml,
    _build_repository_xml,
    _build_texture_xml,
    _normalize_texture_format,
    _resource_dir,
    _to_int,
    _write_bytes,
    _write_text,
    build_material_xml,
    write_repo_skeleton,
)


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return str(path)


def _unique_parameter_name(candidate: str, used_names: set, extra_seed: int):
    name = str(candidate or "").strip()
    if name and name not in used_names:
        used_names.add(name)
        return name, extra_seed

    while True:
        fallback = f"tExtraMap{extra_seed}"
        extra_seed += 1
        if fallback not in used_names:
            used_names.add(fallback)
            return fallback, extra_seed


def export_messiah_from_bundle(bundle_dir, out_dir, event_id=None):
    bundle_root = resolve_bundle_root(bundle_dir)
    manifest, materials_payload = load_bundle_payload(bundle_root)
    event_id = detect_event_id(bundle_root, explicit_event_id=event_id, manifest=manifest)

    mesh_info = parse_obj_mesh(bundle_root / "mesh" / "mesh.obj")

    repo_root = write_repo_skeleton(Path(out_dir) / "messiah", event_id)

    mesh_guid = hash_guid("Mesh", event_id, "mesh")
    material_guid = hash_guid("Material", event_id, "material")
    model_guid = hash_guid("Model", event_id, "model")

    mesh_dir = _resource_dir(repo_root, "Mesh", mesh_guid)
    mesh_dir.mkdir(parents=True, exist_ok=True)
    mesh_xml = _build_mesh_xml(
        mesh_info["vertex_count"],
        mesh_info["index_count"],
        len(mesh_info["vertex_bytes"]),
        len(mesh_info["index_bytes"]),
    )
    _write_text(mesh_dir / "resource.xml", mesh_xml)
    _write_bytes(mesh_dir / "resource.data", mesh_info["vertex_bytes"] + mesh_info["index_bytes"])

    texture_entries = collect_material_textures(materials_payload)
    texture_refs = []
    texture_bindings = []
    used_param_names = set()
    extra_seed = 0
    exported_texture_records = []
    missing_texture_records = []

    for index, texture_entry in enumerate(texture_entries):
        param_hint = map_texture_slot_to_parameter(texture_entry, index)
        parameter_name, extra_seed = _unique_parameter_name(param_hint, used_param_names, extra_seed)

        source_file = resolve_texture_source(bundle_root, texture_entry)
        if source_file is None:
            missing_texture_records.append(
                {
                    "index": index,
                    "parameter": parameter_name,
                    "slot": texture_entry.get("slot"),
                    "sampler": texture_entry.get("sampler"),
                    "texture_id": texture_entry.get("texture_id"),
                    "source_path": texture_entry.get("source_path"),
                    "output_path": texture_entry.get("output_path"),
                    "status": texture_entry.get("status"),
                    "reason": "source_not_found",
                }
            )
            continue

        texture_key = source_file.name
        texture_guid = hash_guid("Texture", event_id, texture_key)
        texture_refs.append((texture_guid, texture_key, texture_entry))
        texture_bindings.append((parameter_name, texture_guid))

        tex_bytes = source_file.read_bytes()
        width = _to_int(texture_entry.get("width"), 1)
        height = _to_int(texture_entry.get("height"), 1)
        format_name = texture_entry.get("format") or "R8G8B8A8"
        format_name = _normalize_texture_format(str(format_name))

        texture_dir = _resource_dir(repo_root, "Texture", texture_guid)
        texture_dir.mkdir(parents=True, exist_ok=True)
        texture_xml = _build_texture_xml(width, height, format_name, len(tex_bytes))
        _write_text(texture_dir / "texture.xml", texture_xml)
        _write_bytes(texture_dir / "resource.data", tex_bytes)

        exported_texture_records.append(
            {
                "index": index,
                "parameter": parameter_name,
                "texture_guid": texture_guid,
                "source": _safe_rel(source_file, bundle_root),
                "slot": texture_entry.get("slot"),
                "sampler": texture_entry.get("sampler"),
                "texture_id": texture_entry.get("texture_id"),
                "format": format_name,
                "width": width,
                "height": height,
                "size": len(tex_bytes),
            }
        )

    shader_stages = collect_shader_stages(manifest, materials_payload)
    material_template = infer_material_template(manifest, materials_payload, fallback="unlit")

    base_texture_guid = texture_bindings[0][1] if texture_bindings else None
    material_xml = build_material_xml(
        material_template,
        "unlit",
        base_texture_guid,
        texture_bindings=texture_bindings,
    )
    material_dir = _resource_dir(repo_root, "Material", material_guid)
    material_dir.mkdir(parents=True, exist_ok=True)
    _write_text(material_dir / "resource.xml", material_xml)

    model_xml = _build_model_xml(
        mesh_guid,
        material_guid,
        mesh_info["vertex_count"],
        mesh_info["index_count"],
    )
    model_dir = _resource_dir(repo_root, "Model", model_guid)
    model_dir.mkdir(parents=True, exist_ok=True)
    _write_text(model_dir / "resource.xml", model_xml)

    repository_xml = _build_repository_xml(event_id, mesh_guid, material_guid, model_guid, texture_refs)
    _write_text(repo_root / "resource.repository", repository_xml)

    mapping_payload = {
        "schema_version": "1.1",
        "event_id": event_id,
        "api": manifest.get("api") if isinstance(manifest, dict) else None,
        "shader_stages": shader_stages,
        "material_template": material_template,
        "material_guid": material_guid,
        "textures": {
            "exported": exported_texture_records,
            "missing": missing_texture_records,
            "count_exported": len(exported_texture_records),
            "count_missing": len(missing_texture_records),
        },
    }
    _write_text(repo_root / "import_bundle_mapping.json", json.dumps(mapping_payload, indent=2, ensure_ascii=False))

    return repo_root


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export Messiah assets from import_bundle output")
    parser.add_argument("--bundle", required=True, help="Path to import_bundle directory or event root")
    parser.add_argument("--out", required=True, help="Output root directory")
    parser.add_argument("--event", required=False, type=int, help="Optional event id override")
    args = parser.parse_args(argv)

    repo_root = export_messiah_from_bundle(args.bundle, args.out, event_id=args.event)
    print(f"[OK] messiah repository generated: {repo_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
