import argparse
import json
import os
from pathlib import Path


def _parse_event_id_from_path(intermediate_path):
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


def _pick_event_id(intermediate_path):
    event_id = _parse_event_id_from_path(intermediate_path)
    if event_id is not None:
        return event_id

    candidates = []
    for child in intermediate_path.iterdir():
        if child.is_dir() and child.name.startswith("event_"):
            suffix = child.name.split("_", 1)[1]
            if not suffix.isdigit():
                continue
            test_dir = child / "intermediate" / "mesh" / "mesh.json"
            if test_dir.exists():
                candidates.append(int(suffix))
    if candidates:
        return min(candidates)
    raise ValueError("event_id not provided and no event_* folders found")


def _resolve_intermediate_path(base_path, event_id):
    if base_path.name == "intermediate":
        return base_path
    candidate = base_path / "intermediate"
    if candidate.exists():
        return candidate
    if event_id is not None:
        candidate = base_path / f"event_{event_id}" / "intermediate"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("intermediate directory not found")


def _load_mesh(intermediate_path):
    mesh_path = intermediate_path / "mesh" / "mesh.json"
    if not mesh_path.exists():
        raise FileNotFoundError(f"mesh.json not found: {mesh_path}")
    mesh_blob = json.loads(mesh_path.read_text(encoding="utf-8"))
    return mesh_blob.get("mesh", {})


def _compute_stats(intermediate_path):
    mesh = _load_mesh(intermediate_path)
    vertex_count = int(mesh.get("vertex_count", 0))
    index_count = int(mesh.get("index_count", 0))
    triangle_count = index_count // 3 if index_count else 0
    material_path = intermediate_path / "materials" / "material.json"
    texture_slots = 0
    if material_path.exists():
        material = json.loads(material_path.read_text(encoding="utf-8")).get("material", {})
        textures = material.get("textures") or []
        texture_slots = len(textures)
    return {
        "vertex_count": vertex_count,
        "index_count": index_count,
        "triangle_count": triangle_count,
        "texture_slots": texture_slots,
    }


def export_fbx_assets(intermediate_dir, out_dir, event_id, allow_missing_backend=False):
    from converters.obj_writer import write_obj
    from converters.fbx_profiles import build_profile
    from converters.fbx_sdk_bridge import resolve_fbx_backend, convert_obj_to_fbx

    intermediate_path = Path(intermediate_dir)
    if event_id is None:
        event_id = _pick_event_id(intermediate_path)
    intermediate_path = _resolve_intermediate_path(intermediate_path, event_id)

    obj_root = write_obj(str(intermediate_path), str(out_dir), event_id)
    event_root = Path(out_dir) / f"event_{event_id}"
    stats = _compute_stats(intermediate_path)
    stats_path = event_root / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    fbx_root = event_root / "fbx"
    unity_dir = fbx_root / "unity"
    unreal_dir = fbx_root / "unreal"
    unity_dir.mkdir(parents=True, exist_ok=True)
    unreal_dir.mkdir(parents=True, exist_ok=True)

    backend = resolve_fbx_backend()
    if backend == "none":
        if allow_missing_backend:
            return 0
        raise RuntimeError("FBX backend not available. Set FBX_SDK_ROOT or install fbx bindings.")

    unity_profile = build_profile("unity")
    unreal_profile = build_profile("unreal")

    convert_obj_to_fbx(obj_root / "mesh.obj", unity_dir / "mesh.fbx", unity_profile, backend)
    convert_obj_to_fbx(obj_root / "mesh.obj", unreal_dir / "mesh.fbx", unreal_profile, backend)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export FBX assets from intermediate output")
    parser.add_argument("--intermediate", required=True, help="Intermediate directory")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--event", required=False, help="Event ID")
    args = parser.parse_args(argv)

    allow_missing = os.environ.get("RDC_FBX_ALLOW_MISSING") == "1"
    event_id = int(args.event) if args.event else None
    return export_fbx_assets(args.intermediate, args.out, event_id, allow_missing_backend=allow_missing)
