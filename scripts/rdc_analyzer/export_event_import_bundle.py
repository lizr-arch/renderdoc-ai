import argparse
import json
import shutil
from pathlib import Path

from converters.obj_writer import write_obj
from decoders.texture_decoder import decode_texture, save_as_png
from extract_event_intermediate import extract_event_intermediate, validate_json_file


_SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".dds", ".ktx", ".ktx2", ".astc"}


def _parse_event_id_from_path(intermediate_path: Path):
    if intermediate_path.name == "intermediate":
        parent = intermediate_path.parent
        if parent.name.startswith("event_"):
            suffix = parent.name.split("_", 1)[1]
            if suffix.isdigit():
                return int(suffix)
    if intermediate_path.name.startswith("event_"):
        suffix = intermediate_path.name.split("_", 1)[1]
        if suffix.isdigit():
            return int(suffix)
    return None


def _pick_event_id(base_path: Path):
    event_id = _parse_event_id_from_path(base_path)
    if event_id is not None:
        return event_id

    candidates = []
    for child in base_path.iterdir():
        if child.is_dir() and child.name.startswith("event_"):
            suffix = child.name.split("_", 1)[1]
            if not suffix.isdigit():
                continue
            marker = child / "intermediate" / "mesh" / "mesh.json"
            if marker.exists():
                candidates.append(int(suffix))
    if candidates:
        return min(candidates)

    raise ValueError("event_id not provided and no event_* folders found")


def _resolve_intermediate_path(base_path: Path, event_id: int):
    if base_path.name == "intermediate":
        return base_path

    candidate = base_path / "intermediate"
    if candidate.exists():
        return candidate

    candidate = base_path / f"event_{event_id}" / "intermediate"
    if candidate.exists():
        return candidate

    raise FileNotFoundError("intermediate directory not found")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_stem(path_name: str, fallback: str):
    stem = Path(path_name).stem if path_name else ""
    keep = []
    for char in stem:
        if char.isalnum() or char in ("_", "-", "."):
            keep.append(char)
        else:
            keep.append("_")
    clean = "".join(keep).strip("_")
    return clean or fallback


def _to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_source_kind_list(value: str | None):
    if not value:
        return set()

    tokens = []
    for chunk in str(value).replace(";", ",").split(","):
        token = chunk.strip()
        if token:
            tokens.append(token)
    return set(tokens)


def _resolve_optional_path(base_dir: Path, path_value: str, extra_roots: list[Path] | None = None):
    if not path_value:
        return None

    raw = Path(path_value)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        for root in extra_roots or []:
            candidates.append(root / raw)
            candidates.append(root / "textures" / raw)
        candidates.append(base_dir / raw)
        candidates.append(base_dir / "textures" / raw)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else None


def _discover_default_rgba_manifest(intermediate_path: Path):
    event_root = intermediate_path.parent
    candidates = [
        event_root / "rgba" / "rgba_manifest.json",
        event_root / "rgba_manifest.json",
        intermediate_path / "rgba_manifest.json",
        intermediate_path / "textures" / "rgba_manifest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_rgba_overrides(rgba_manifest, intermediate_path: Path):
    if not rgba_manifest:
        return []

    manifest_path = Path(rgba_manifest)
    if not manifest_path.is_absolute():
        manifest_path = Path.cwd() / manifest_path

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = payload
    if isinstance(payload, dict):
        items = payload.get("textures", [])

    overrides = []
    if not isinstance(items, list):
        return overrides

    for item in items:
        if not isinstance(item, dict):
            continue

        file_path = _resolve_optional_path(
            intermediate_path,
            str(item.get("rgba_path") or item.get("path") or ""),
            extra_roots=[manifest_path.parent],
        )
        overrides.append(
            {
                "texture_id": _to_int(item.get("texture_id"), default=0),
                "slot": str(item.get("slot") or ""),
                "file_path": file_path,
                "width": _to_int(item.get("width"), default=0),
                "height": _to_int(item.get("height"), default=0),
                "row_pitch": _to_int(item.get("row_pitch"), default=0),
            }
        )

    return overrides


def _pick_rgba_override(entry: dict, intermediate_path: Path, rgba_overrides: list[dict]):
    texture_id = _to_int(entry.get("texture_id"), default=0)
    slot = str(entry.get("slot") or "")
    default_width = _to_int(entry.get("rgba_width") or entry.get("width"), default=0)
    default_height = _to_int(entry.get("rgba_height") or entry.get("height"), default=0)
    default_row_pitch = _to_int(entry.get("rgba_row_pitch"), default=0)

    inline_path = str(entry.get("rgba_path") or "")
    if inline_path:
        return {
            "texture_id": texture_id,
            "slot": slot,
            "file_path": _resolve_optional_path(intermediate_path, inline_path),
            "width": default_width,
            "height": default_height,
            "row_pitch": default_row_pitch,
        }

    auto_file_candidates = []
    if texture_id > 0:
        auto_file_candidates.extend(
            [
                intermediate_path / "textures" / f"tex_{texture_id}.rgba",
                intermediate_path.parent / "rgba" / f"tex_{texture_id}.rgba",
                intermediate_path.parent / f"tex_{texture_id}.rgba",
            ]
        )

    for candidate in auto_file_candidates:
        if candidate.exists():
            return {
                "texture_id": texture_id,
                "slot": slot,
                "file_path": candidate,
                "width": default_width,
                "height": default_height,
                "row_pitch": default_row_pitch,
            }

    if not rgba_overrides:
        return None

    exact = None
    by_slot = None
    by_id = None
    for override in rgba_overrides:
        override_id = _to_int(override.get("texture_id"), default=0)
        override_slot = str(override.get("slot") or "")

        if override_id > 0 and override_id == texture_id and override_slot and override_slot == slot:
            exact = override
            break
        if by_slot is None and override_slot and override_slot == slot:
            by_slot = override
        if by_id is None and override_id > 0 and override_id == texture_id:
            by_id = override

    return exact or by_slot or by_id


def _pack_rgba_bytes(raw_bytes: bytes, width: int, height: int, row_pitch: int = 0):
    if width <= 0 or height <= 0:
        return None

    expected = width * height * 4
    if row_pitch >= width * 4 and len(raw_bytes) >= row_pitch * height:
        out = bytearray(expected)
        for row in range(height):
            src_start = row * row_pitch
            src_end = src_start + width * 4
            dst_start = row * width * 4
            dst_end = dst_start + width * 4
            out[dst_start:dst_end] = raw_bytes[src_start:src_end]
        return bytes(out)

    if len(raw_bytes) >= expected:
        return raw_bytes[:expected]

    return None


def _export_texture_entry(
    intermediate_path: Path,
    textures_dir: Path,
    entry: dict,
    index: int,
    rgba_overrides: list[dict] | None = None,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
):
    texture_id = int(entry.get("texture_id", index))
    source_path = str(entry.get("path") or f"tex_{texture_id}.bin")
    src_file = intermediate_path / "textures" / source_path

    slot = str(entry.get("slot") or f"slot_{index}")
    sampler = str(entry.get("sampler") or "")
    format_name = str(entry.get("format") or entry.get("format_name") or "")
    source_kind = str(entry.get("source_kind") or "")
    zip_entry = str(entry.get("zip_entry") or "")
    width = int(entry.get("width") or 0)
    height = int(entry.get("height") or 0)

    mode = str(texture_mode or "auto").strip().lower()
    if mode not in {"auto", "decoded", "raw"}:
        raise ValueError(f"unsupported texture_mode: {texture_mode}")

    raw_kinds = raw_source_kinds or set()
    force_raw = mode == "raw"
    if mode == "auto" and source_kind and source_kind in raw_kinds:
        force_raw = True

    result = {
        "slot": slot,
        "sampler": sampler,
        "texture_id": texture_id,
        "source_path": source_path,
        "output_path": "",
        "status": "missing",
        "width": width,
        "height": height,
        "format": format_name,
    }
    if source_kind:
        result["source_kind"] = source_kind
    if zip_entry:
        result["zip_entry"] = zip_entry

    textures_dir.mkdir(parents=True, exist_ok=True)
    base_name = _safe_stem(source_path, f"tex_{texture_id}")

    rgba_override = _pick_rgba_override(entry, intermediate_path, rgba_overrides or [])
    if rgba_override:
        rgba_file = rgba_override.get("file_path")
        override_width = _to_int(rgba_override.get("width"), default=width)
        override_height = _to_int(rgba_override.get("height"), default=height)
        row_pitch = _to_int(rgba_override.get("row_pitch"), default=0)

        if isinstance(rgba_file, Path) and rgba_file.exists() and override_width > 0 and override_height > 0:
            rgba_bytes = _pack_rgba_bytes(
                rgba_file.read_bytes(),
                width=override_width,
                height=override_height,
                row_pitch=row_pitch,
            )
            if rgba_bytes:
                out_name = f"{base_name}.png"
                dst = textures_dir / out_name
                save_as_png(rgba_bytes, override_width, override_height, dst)
                result["output_path"] = f"textures/{out_name}"
                result["status"] = "rgba_bytes_png"
                result["width"] = override_width
                result["height"] = override_height
                result["format"] = "RGBA8"
                return result

    if not src_file.exists():
        result["status"] = "missing_source"
        return result

    src_suffix = src_file.suffix.lower()
    src_data = src_file.read_bytes()

    if not src_data and src_suffix not in _IMAGE_SUFFIXES:
        result["status"] = "missing_source"
        return result

    if src_suffix in _IMAGE_SUFFIXES:
        out_name = f"{base_name}{src_suffix}"
        dst = textures_dir / out_name
        dst.write_bytes(src_data)
        result["output_path"] = f"textures/{out_name}"
        result["status"] = "copied_image"
        return result

    if not force_raw and width > 0 and height > 0 and format_name:
        try:
            rgba = decode_texture(src_data, width, height, format_name)
            out_name = f"{base_name}.png"
            dst = textures_dir / out_name
            save_as_png(rgba, width, height, dst)
            result["output_path"] = f"textures/{out_name}"
            result["status"] = "decoded_rgba8_png"
            return result
        except Exception:
            pass

    out_name = f"{base_name}.bin"
    dst = textures_dir / out_name
    shutil.copy2(src_file, dst)
    result["output_path"] = f"textures/{out_name}"
    result["status"] = "raw_copy"
    return result


def _export_materials_bundle(
    intermediate_path: Path,
    bundle_root: Path,
    event_id: int,
    rgba_overrides: list[dict] | None = None,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
):
    material_blob = _load_json(intermediate_path / "materials" / "material.json", {})
    material = material_blob.get("material", {}) if isinstance(material_blob, dict) else {}

    material_name = str(material.get("name") or f"event_{event_id}_material_0")
    shader_name = str(material.get("shader") or "unknown")
    constants = list(material.get("constants") or [])
    textures = list(material.get("textures") or [])

    textures_dir = bundle_root / "textures"
    exported_textures = []
    for index, texture_entry in enumerate(textures):
        if not isinstance(texture_entry, dict):
            continue
        exported_textures.append(
            _export_texture_entry(
                intermediate_path,
                textures_dir,
                texture_entry,
                index,
                rgba_overrides=rgba_overrides,
                texture_mode=texture_mode,
                raw_source_kinds=raw_source_kinds,
            )
        )

    payload = {
        "schema_version": "1.0",
        "schema_path": "schema/import_bundle_materials.schema.json",
        "event_id": int(event_id),
        "materials": [
            {
                "name": material_name,
                "shader": shader_name,
                "textures": exported_textures,
                "constants": constants,
            }
        ],
    }

    material_dir = bundle_root / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    material_path = material_dir / "materials.json"
    material_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validate_json_file(material_path, _SCHEMA_DIR / "import_bundle_materials.schema.json")
    return payload, exported_textures


def _export_shader_bundle(intermediate_path: Path, bundle_root: Path):
    src_shader_dir = intermediate_path / "shaders"
    out_shader_dir = bundle_root / "shaders"
    out_shader_dir.mkdir(parents=True, exist_ok=True)

    if not src_shader_dir.exists():
        return []

    shader_files = []
    for src in sorted(src_shader_dir.iterdir()):
        if src.is_file():
            dst = out_shader_dir / src.name
            shutil.copy2(src, dst)
            shader_files.append(src.name)

    shader_entries = []
    for name in shader_files:
        if not name.lower().endswith(".json"):
            continue
        shader_blob = _load_json(out_shader_dir / name, {})
        shader = shader_blob.get("shader", {}) if isinstance(shader_blob, dict) else {}
        stage = str(shader.get("stage") or Path(name).stem)
        shader_entries.append(
            {
                "stage": stage,
                "json": f"shaders/{name}",
                "bytecode_format": str(shader.get("bytecode_format") or "unknown"),
                "entry": str(shader.get("entry") or ""),
            }
        )

    return shader_entries


def _load_mesh_stats(intermediate_path: Path):
    mesh_blob = _load_json(intermediate_path / "mesh" / "mesh.json", {})
    mesh = mesh_blob.get("mesh", {}) if isinstance(mesh_blob, dict) else {}
    vertex_count = int(mesh.get("vertex_count") or 0)
    index_count = int(mesh.get("index_count") or 0)
    return {
        "vertex_count": vertex_count,
        "index_count": index_count,
        "triangle_count": index_count // 3 if index_count > 0 else 0,
    }


def export_event_import_bundle(
    intermediate_dir,
    out_dir,
    event_id=None,
    rgba_manifest=None,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
):
    base_path = Path(intermediate_dir)
    if event_id is None:
        event_id = _pick_event_id(base_path)
    event_id = int(event_id)

    intermediate_path = _resolve_intermediate_path(base_path, event_id)

    out_root = Path(out_dir)
    event_root = out_root / f"event_{event_id}"
    bundle_root = event_root / "import_bundle"
    mesh_out_dir = bundle_root / "mesh"
    mesh_out_dir.mkdir(parents=True, exist_ok=True)

    obj_root = write_obj(str(intermediate_path), str(out_root), event_id)
    obj_path = obj_root / "mesh.obj"
    mtl_path = obj_root / "mesh.mtl"

    mesh_obj_out = mesh_out_dir / "mesh.obj"
    mesh_mtl_out = mesh_out_dir / "mesh.mtl"
    shutil.copy2(obj_path, mesh_obj_out)
    if mtl_path.exists():
        shutil.copy2(mtl_path, mesh_mtl_out)

    effective_rgba_manifest = rgba_manifest
    if not effective_rgba_manifest:
        discovered_manifest = _discover_default_rgba_manifest(intermediate_path)
        if discovered_manifest is not None:
            effective_rgba_manifest = str(discovered_manifest)

    rgba_overrides = _load_rgba_overrides(effective_rgba_manifest, intermediate_path)

    mode = str(texture_mode or "auto").strip().lower()
    if mode not in {"auto", "decoded", "raw"}:
        raise ValueError(f"unsupported texture_mode: {texture_mode}")

    source_kind_set = set(raw_source_kinds or set())
    materials_payload, exported_textures = _export_materials_bundle(
        intermediate_path,
        bundle_root,
        event_id,
        rgba_overrides=rgba_overrides,
        texture_mode=mode,
        raw_source_kinds=source_kind_set,
    )
    shader_entries = _export_shader_bundle(intermediate_path, bundle_root)

    source_manifest = _load_json(intermediate_path.parent / "manifest.json", {})
    mesh_stats = _load_mesh_stats(intermediate_path)

    manifest = {
        "schema_version": "1.0",
        "schema_path": "schema/import_bundle_manifest.schema.json",
        "event_id": event_id,
        "api": str(source_manifest.get("api") or "Unknown"),
        "sources": {
            "intermediate_dir": str(intermediate_path),
            "zip_xml": str((source_manifest.get("sources") or {}).get("zip_xml") or ""),
            "zip_bin": str((source_manifest.get("sources") or {}).get("zip_bin") or ""),
            "rgba_manifest": str(effective_rgba_manifest or ""),
        },
        "options": {
            "texture_mode": mode,
            "raw_source_kinds": sorted(source_kind_set),
        },
        "outputs": {
            "mesh_obj": "mesh/mesh.obj",
            "mesh_mtl": "mesh/mesh.mtl" if mesh_mtl_out.exists() else "",
            "materials": "materials/materials.json",
            "shaders": "shaders/",
            "textures": "textures/",
        },
        "statistics": {
            **mesh_stats,
            "shader_count": len(shader_entries),
            "texture_count": len(exported_textures),
            "decoded_texture_count": len([entry for entry in exported_textures if entry.get("status") in {"decoded_rgba8_png", "rgba_bytes_png"}]),
        },
        "materials": materials_payload.get("materials", []),
        "shaders": shader_entries,
    }

    manifest_path = bundle_root / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    validate_json_file(manifest_path, _SCHEMA_DIR / "import_bundle_manifest.schema.json")
    return bundle_root


def _extract_then_export(
    xml_path,
    zip_path,
    event_id: int,
    out_dir,
    vertex_stride: int = 0,
    rgba_manifest=None,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
):
    intermediate_path = extract_event_intermediate(
        xml_path=xml_path,
        zip_path=zip_path,
        event_id=event_id,
        out_dir=out_dir,
        vertex_stride=vertex_stride,
    )
    return export_event_import_bundle(
        intermediate_path,
        out_dir,
        event_id=event_id,
        rgba_manifest=rgba_manifest,
        texture_mode=texture_mode,
        raw_source_kinds=raw_source_kinds,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export single-event import bundle from intermediate or zip.xml+zip")
    parser.add_argument("--intermediate", required=False, help="Path to intermediate folder (or event root)")
    parser.add_argument("--xml", required=False, help="Path to capture.zip.xml")
    parser.add_argument("--zip", required=False, help="Path to capture.zip")
    parser.add_argument("--event", required=False, type=int, help="Target event id")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--vertex-stride", required=False, type=int, default=0, help="Optional vertex stride hint for zip.xml extraction")
    parser.add_argument("--rgba-manifest", required=False, help="Optional JSON mapping for external RGBA bytes overrides; if omitted, auto-discover event_<id>/rgba/rgba_manifest.json")
    parser.add_argument(
        "--texture-mode",
        required=False,
        choices=["auto", "decoded", "raw"],
        default="auto",
        help="Texture export mode: auto (default), decoded (prefer png), raw (always .bin for non-image)",
    )
    parser.add_argument(
        "--raw-source-kinds",
        required=False,
        default="",
        help="Comma-separated source_kind values that force raw export when --texture-mode=auto",
    )
    args = parser.parse_args(argv)

    raw_source_kinds = _parse_source_kind_list(args.raw_source_kinds)

    if args.intermediate:
        bundle_root = export_event_import_bundle(
            intermediate_dir=args.intermediate,
            out_dir=args.out,
            event_id=args.event,
            rgba_manifest=args.rgba_manifest,
            texture_mode=args.texture_mode,
            raw_source_kinds=raw_source_kinds,
        )
    else:
        if not args.xml or not args.zip or args.event is None:
            raise ValueError("When --intermediate is not provided, --xml --zip --event are required")
        bundle_root = _extract_then_export(
            xml_path=args.xml,
            zip_path=args.zip,
            event_id=int(args.event),
            out_dir=args.out,
            vertex_stride=int(args.vertex_stride),
            rgba_manifest=args.rgba_manifest,
            texture_mode=args.texture_mode,
            raw_source_kinds=raw_source_kinds,
        )

    print(f"[OK] import bundle generated: {bundle_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
