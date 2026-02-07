import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))

from engine_guid import hash_guid
from messiah_bundle_adapter import (
    collect_material_textures,
    detect_event_id,
    load_bundle_payload,
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
    for texture_entry in texture_entries:
        source_file = resolve_texture_source(bundle_root, texture_entry)
        if source_file is None:
            continue

        texture_key = source_file.name
        texture_guid = hash_guid("Texture", event_id, texture_key)
        texture_refs.append((texture_guid, texture_key, texture_entry))

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

    shader_kind = None
    shaders = manifest.get("shaders") if isinstance(manifest, dict) else None
    if isinstance(shaders, list) and shaders:
        first_shader = shaders[0] if isinstance(shaders[0], dict) else {}
        shader_kind = first_shader.get("stage")

    base_texture_guid = texture_refs[0][0] if texture_refs else None
    material_xml = build_material_xml(shader_kind, "unlit", base_texture_guid)
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
