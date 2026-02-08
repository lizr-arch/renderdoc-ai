import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
if str(EXPORTERS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPORTERS_DIR))

try:
    from spirv_cross_bridge import resolve_spirv_cross_path, run_spirv_cross
except Exception:
    resolve_spirv_cross_path = None
    run_spirv_cross = None


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


def _load_shader_entries(intermediate_path):
    shader_dir = intermediate_path / "shaders"
    if not shader_dir.exists():
        return []

    entries = []
    for shader_json in sorted(shader_dir.glob("*.json")):
        try:
            blob = json.loads(shader_json.read_text(encoding="utf-8"))
        except Exception:
            continue

        shader = blob.get("shader", {}) if isinstance(blob, dict) else {}
        if not isinstance(shader, dict):
            continue

        stage = str(shader.get("stage") or shader_json.stem)
        source_kind = str(shader.get("source_kind") or "")
        bytecode_format = str(shader.get("bytecode_format") or "")
        entry_name = str(shader.get("entry") or "")
        source_resource_id = int(shader.get("source_resource_id") or shader.get("resource_id") or 0)
        source_bin = str(shader.get("path") or f"{stage}.bin")

        entries.append(
            {
                "stage": stage,
                "source_kind": source_kind,
                "bytecode_format": bytecode_format,
                "entry": entry_name,
                "source_resource_id": source_resource_id,
                "source_json": f"intermediate/shaders/{shader_json.name}",
                "source_bin": f"intermediate/shaders/{source_bin}",
            }
        )

    return entries


def _build_shader_route(shader_entry, engine):
    source_kind = str(shader_entry.get("source_kind") or "")
    bytecode_format = str(shader_entry.get("bytecode_format") or "").lower()

    output_ext = ".hlsl" if engine == "unity" else ".usf"
    stage = str(shader_entry.get("stage") or "unknown")

    if source_kind in {"vulkan_shader_object", "vulkan_shader_module"} or "spirv" in bytecode_format:
        strategy = "spirv_to_hlsl"
        tool = "spirv-cross"
    elif source_kind == "d3d11_shader_bytecode" or bytecode_format in {"dxbc", "dxil"}:
        strategy = "dxbc_to_hlsl"
        tool = "dxbc-toolchain"
    else:
        strategy = "manual_review"
        tool = ""

    return {
        **shader_entry,
        "engine": engine,
        "strategy": strategy,
        "tool": tool,
        "output_source": f"shaders/{stage}{output_ext}",
    }


def _write_shader_import_plan(intermediate_path, event_root, engine, engine_dir):
    shader_entries = _load_shader_entries(intermediate_path)
    routed = [_build_shader_route(entry, engine) for entry in shader_entries]
    plan = {
        "schema_version": "1.0",
        "event_id": int(event_root.name.split("_", 1)[1]) if event_root.name.startswith("event_") else 0,
        "engine": engine,
        "intermediate": str(intermediate_path),
        "shader_count": len(routed),
        "shaders": routed,
    }
    plan_path = engine_dir / "shader_import_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan_path


def _resolve_shader_source_path(intermediate_path, source_bin):
    rel = str(source_bin or "").replace("\\", "/")
    candidates = []
    if rel:
        rel_path = Path(rel)
        candidates.append(intermediate_path / rel_path)
        candidates.append(intermediate_path.parent / rel_path)
        candidates.append(intermediate_path / "shaders" / rel_path.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    if candidates:
        return candidates[0]
    return None


def _write_shader_stub(output_path, route, reason):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "// Auto-generated shader placeholder",
        f"// stage: {route.get('stage', 'unknown')}",
        f"// strategy: {route.get('strategy', '')}",
        f"// source_kind: {route.get('source_kind', '')}",
        f"// source_bin: {route.get('source_bin', '')}",
        f"// reason: {reason}",
        "",
        "// TODO: replace this file with converted shader source.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _execute_shader_import_plan(intermediate_path, plan_path, spirv_cross_cli_path=None):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    routes = list(plan.get("shaders") or [])

    spirv_path = ""
    if callable(resolve_spirv_cross_path):
        spirv_path = str(resolve_spirv_cross_path(spirv_cross_cli_path) or "")
    elif spirv_cross_cli_path:
        spirv_path = str(spirv_cross_cli_path)

    status_counts = {}

    for route in routes:
        strategy = str(route.get("strategy") or "manual_review")
        output_rel = str(route.get("output_source") or "")
        if not output_rel:
            stage = str(route.get("stage") or "unknown")
            output_rel = f"shaders/{stage}.txt"
            route["output_source"] = output_rel

        output_path = plan_path.parent / output_rel
        source_path = _resolve_shader_source_path(intermediate_path, route.get("source_bin"))
        source_exists = bool(source_path and source_path.exists())

        status = "manual_review"
        message = ""

        if strategy == "spirv_to_hlsl":
            if not source_exists:
                status = "missing_source"
                message = "source SPIR-V binary not found"
                _write_shader_stub(output_path, route, message)
            elif not spirv_path or not callable(run_spirv_cross):
                status = "missing_spirv_cross"
                message = "spirv-cross not available"
                _write_shader_stub(output_path, route, message)
            else:
                try:
                    source_text = run_spirv_cross(spirv_path, source_path.read_bytes())
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(source_text, encoding="utf-8")
                    status = "converted"
                    message = "converted by spirv-cross"
                except Exception as exc:
                    status = "spirv_cross_failed"
                    message = str(exc)
                    _write_shader_stub(output_path, route, message)
        elif strategy == "dxbc_to_hlsl":
            status = "stubbed_dxbc"
            message = "dxbc conversion adapter placeholder"
            _write_shader_stub(output_path, route, message)
        else:
            status = "manual_review"
            message = "no automatic converter configured"
            _write_shader_stub(output_path, route, message)

        route["status"] = status
        route["message"] = message
        route["generated_file"] = output_rel.replace("\\", "/")
        route["source_exists"] = bool(source_exists)
        route["resolved_source"] = str(source_path) if source_path else ""

        status_counts[status] = int(status_counts.get(status, 0)) + 1

    plan["shaders"] = routes
    plan["execution"] = {
        "spirv_cross": spirv_path,
        "status_counts": status_counts,
    }
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan_path


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


def export_fbx_assets(intermediate_dir, out_dir, event_id, allow_missing_backend=False, spirv_cross_path=None):
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

    unity_plan_path = _write_shader_import_plan(intermediate_path, event_root, "unity", unity_dir)
    unreal_plan_path = _write_shader_import_plan(intermediate_path, event_root, "unreal", unreal_dir)

    _execute_shader_import_plan(intermediate_path, unity_plan_path, spirv_cross_cli_path=spirv_cross_path)
    _execute_shader_import_plan(intermediate_path, unreal_plan_path, spirv_cross_cli_path=spirv_cross_path)

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
    parser.add_argument("--spirv-cross", required=False, help="Path to spirv-cross executable")
    args = parser.parse_args(argv)

    allow_missing = os.environ.get("RDC_FBX_ALLOW_MISSING") == "1"
    event_id = int(args.event) if args.event else None
    return export_fbx_assets(
        args.intermediate,
        args.out,
        event_id,
        allow_missing_backend=allow_missing,
        spirv_cross_path=args.spirv_cross,
    )

if __name__ == "__main__":
    raise SystemExit(main())
