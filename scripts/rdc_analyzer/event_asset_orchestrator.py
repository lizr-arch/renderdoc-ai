import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from export_event_import_bundle import export_event_import_bundle
from export_fbx_assets import export_fbx_assets
from extract_event_intermediate import extract_event_intermediate, validate_json_file


_SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
_ARTIFACT_SCHEMA_PATH = _SCHEMA_DIR / "artifact_index.schema.json"


def _parse_event_id_from_path(path: Path):
    if path.name == "intermediate":
        parent = path.parent
        if parent.name.startswith("event_"):
            suffix = parent.name.split("_", 1)[1]
            if suffix.isdigit():
                return int(suffix)
    if path.name.startswith("event_"):
        suffix = path.name.split("_", 1)[1]
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


def _parse_source_kind_list(value: str | None):
    if not value:
        return set()

    tokens = []
    for chunk in str(value).replace(";", ",").split(","):
        token = chunk.strip()
        if token:
            tokens.append(token)
    return set(tokens)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_or_abs(path: Path, root: Path):
    if not path.exists():
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _count_texture_statuses(materials_path: Path):
    payload = _load_json(materials_path, {})
    materials = payload.get("materials") if isinstance(payload, dict) else None

    counts = Counter()
    if isinstance(materials, list):
        for material in materials:
            textures = material.get("textures") if isinstance(material, dict) else None
            if not isinstance(textures, list):
                continue
            for texture in textures:
                if not isinstance(texture, dict):
                    continue
                status = str(texture.get("status") or "other")
                counts[status] += 1

    summary = {
        "decoded_rgba8_png": 0,
        "rgba_bytes_png": 0,
        "copied_image": 0,
        "raw_copy": 0,
        "missing_source": 0,
        "other": 0,
        "total": 0,
    }

    for key, value in counts.items():
        if key in summary:
            summary[key] += int(value)
        else:
            summary["other"] += int(value)

    summary["total"] = (
        summary["decoded_rgba8_png"]
        + summary["rgba_bytes_png"]
        + summary["copied_image"]
        + summary["raw_copy"]
        + summary["missing_source"]
        + summary["other"]
    )

    return summary


def _extract_shader_counts(plan_payload: dict):
    if not isinstance(plan_payload, dict):
        return {}
    execution = plan_payload.get("execution")
    if not isinstance(execution, dict):
        return {}
    status_counts = execution.get("status_counts")
    if not isinstance(status_counts, dict):
        return {}

    result = {}
    for key, value in status_counts.items():
        try:
            result[str(key)] = int(value)
        except Exception:
            continue
    return result


def _count_shader_statuses(unity_plan_path: Path, unreal_plan_path: Path):
    unity_payload = _load_json(unity_plan_path, {})
    unreal_payload = _load_json(unreal_plan_path, {})

    unity_counts = _extract_shader_counts(unity_payload)
    unreal_counts = _extract_shader_counts(unreal_payload)

    total = Counter()
    for key, value in unity_counts.items():
        total[key] += int(value)
    for key, value in unreal_counts.items():
        total[key] += int(value)

    return {
        "unity": unity_counts,
        "unreal": unreal_counts,
        "total": dict(total),
    }


def _detect_fbx_stage_status(event_root: Path, allow_missing_backend: bool):
    unity_fbx = event_root / "fbx" / "unity" / "mesh.fbx"
    unreal_fbx = event_root / "fbx" / "unreal" / "mesh.fbx"

    if unity_fbx.exists() and unreal_fbx.exists():
        return "ok"

    if allow_missing_backend:
        return "degraded_missing_fbx_backend"

    return "failed"


def orchestrate_event_assets(
    *,
    out_dir,
    event_id=None,
    intermediate_dir=None,
    xml_path=None,
    zip_path=None,
    vertex_stride=0,
    rgba_manifest=None,
    texture_mode="auto",
    raw_source_kinds=None,
    allow_missing_fbx_backend=False,
    spirv_cross_path=None,
    fxc_path=None,
    dxc_path=None,
):
    if intermediate_dir:
        if xml_path or zip_path:
            raise ValueError("Provide either --intermediate or --xml/--zip, not both")
    else:
        if not xml_path or not zip_path:
            raise ValueError("When --intermediate is not provided, --xml and --zip are required")

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    stage_results = []
    raw_source_kinds = set(raw_source_kinds or set())

    if intermediate_dir:
        base_path = Path(intermediate_dir)
        if event_id is None:
            event_id = _pick_event_id(base_path)
        event_id = int(event_id)
        intermediate_path = _resolve_intermediate_path(base_path, event_id)
        stage_results.append({"name": "extract_intermediate", "status": "reused", "message": "using existing intermediate"})
    else:
        if event_id is None:
            raise ValueError("--event is required when using --xml/--zip")
        event_id = int(event_id)
        intermediate_path = Path(
            extract_event_intermediate(
                xml_path=xml_path,
                zip_path=zip_path,
                event_id=event_id,
                out_dir=str(out_root),
                vertex_stride=int(vertex_stride),
            )
        )
        stage_results.append({"name": "extract_intermediate", "status": "ok", "message": "intermediate generated"})

    bundle_root = Path(
        export_event_import_bundle(
            intermediate_dir=str(intermediate_path),
            out_dir=str(out_root),
            event_id=event_id,
            rgba_manifest=rgba_manifest,
            texture_mode=texture_mode,
            raw_source_kinds=raw_source_kinds,
        )
    )
    stage_results.append({"name": "export_import_bundle", "status": "ok", "message": "import bundle generated"})

    export_fbx_assets(
        intermediate_dir=str(intermediate_path),
        out_dir=str(out_root),
        event_id=event_id,
        allow_missing_backend=bool(allow_missing_fbx_backend),
        spirv_cross_path=spirv_cross_path,
        fxc_path=fxc_path,
        dxc_path=dxc_path,
    )

    event_root = out_root / f"event_{event_id}"
    fbx_status = _detect_fbx_stage_status(event_root, bool(allow_missing_fbx_backend))
    stage_results.append(
        {
            "name": "export_fbx_assets",
            "status": fbx_status,
            "message": "fbx outputs available" if fbx_status == "ok" else "fbx backend missing, kept obj/import bundle",
        }
    )

    bundle_manifest_path = bundle_root / "bundle_manifest.json"
    materials_path = bundle_root / "materials" / "materials.json"
    stats_path = event_root / "stats.json"
    unity_plan_path = event_root / "fbx" / "unity" / "shader_import_plan.json"
    unreal_plan_path = event_root / "fbx" / "unreal" / "shader_import_plan.json"
    source_manifest_path = event_root / "manifest.json"

    bundle_manifest = _load_json(bundle_manifest_path, {})
    source_manifest = _load_json(source_manifest_path, {})
    bundle_sources = bundle_manifest.get("sources") if isinstance(bundle_manifest, dict) else {}
    source_sources = source_manifest.get("sources") if isinstance(source_manifest, dict) else {}

    api = "Unknown"
    if isinstance(bundle_manifest, dict) and bundle_manifest.get("api"):
        api = str(bundle_manifest.get("api"))
    elif isinstance(source_manifest, dict) and source_manifest.get("api"):
        api = str(source_manifest.get("api"))

    artifact_index = {
        "schema_version": "1.0",
        "schema_path": "schema/artifact_index.schema.json",
        "event_id": int(event_id),
        "api": api,
        "sources": {
            "intermediate_dir": str(intermediate_path),
            "zip_xml": str((bundle_sources or {}).get("zip_xml") or (source_sources or {}).get("zip_xml") or ""),
            "zip_bin": str((bundle_sources or {}).get("zip_bin") or (source_sources or {}).get("zip_bin") or ""),
        },
        "options": {
            "texture_mode": str(texture_mode),
            "raw_source_kinds": sorted(raw_source_kinds),
            "allow_missing_fbx_backend": bool(allow_missing_fbx_backend),
        },
        "stages": stage_results,
        "artifacts": {
            "bundle_manifest": _rel_or_abs(bundle_manifest_path, event_root),
            "mesh_obj": _rel_or_abs(bundle_root / "mesh" / "mesh.obj", event_root),
            "mesh_mtl": _rel_or_abs(bundle_root / "mesh" / "mesh.mtl", event_root),
            "materials": _rel_or_abs(materials_path, event_root),
            "textures_dir": _rel_or_abs(bundle_root / "textures", event_root),
            "unity_fbx": _rel_or_abs(event_root / "fbx" / "unity" / "mesh.fbx", event_root),
            "unreal_fbx": _rel_or_abs(event_root / "fbx" / "unreal" / "mesh.fbx", event_root),
            "unity_shader_plan": _rel_or_abs(unity_plan_path, event_root),
            "unreal_shader_plan": _rel_or_abs(unreal_plan_path, event_root),
            "stats": _rel_or_abs(stats_path, event_root),
        },
        "status_counts": {
            "texture": _count_texture_statuses(materials_path),
            "shader": _count_shader_statuses(unity_plan_path, unreal_plan_path),
        },
        "statistics": {
            "bundle": (bundle_manifest.get("statistics") if isinstance(bundle_manifest, dict) else {}) or {},
            "mesh": _load_json(stats_path, {}),
        },
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    artifact_index_path = event_root / "artifact_index.json"
    artifact_index_path.write_text(json.dumps(artifact_index, indent=2), encoding="utf-8")
    validate_json_file(artifact_index_path, _ARTIFACT_SCHEMA_PATH)

    return artifact_index_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Orchestrate event asset export (intermediate -> bundle -> fbx)")
    parser.add_argument("--intermediate", required=False, help="Path to intermediate folder (or event root)")
    parser.add_argument("--xml", required=False, help="Path to capture.zip.xml")
    parser.add_argument("--zip", required=False, help="Path to capture.zip")
    parser.add_argument("--event", required=False, type=int, help="Target event id")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--vertex-stride", required=False, type=int, default=0, help="Optional vertex stride hint for zip.xml extraction")
    parser.add_argument("--rgba-manifest", required=False, help="Optional JSON mapping for external RGBA bytes overrides")
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
    parser.add_argument("--spirv-cross", required=False, help="Path to spirv-cross executable")
    parser.add_argument("--fxc", required=False, help="Path to fxc executable")
    parser.add_argument("--dxc", required=False, help="Path to dxc executable")
    parser.add_argument(
        "--allow-missing-fbx-backend",
        action="store_true",
        help="Allow missing FBX backend and continue with bundle + shader plans",
    )

    args = parser.parse_args(argv)

    raw_source_kinds = _parse_source_kind_list(args.raw_source_kinds)
    allow_missing_backend = bool(args.allow_missing_fbx_backend or os.environ.get("RDC_FBX_ALLOW_MISSING") == "1")

    artifact_index_path = orchestrate_event_assets(
        out_dir=args.out,
        event_id=args.event,
        intermediate_dir=args.intermediate,
        xml_path=args.xml,
        zip_path=args.zip,
        vertex_stride=int(args.vertex_stride),
        rgba_manifest=args.rgba_manifest,
        texture_mode=args.texture_mode,
        raw_source_kinds=raw_source_kinds,
        allow_missing_fbx_backend=allow_missing_backend,
        spirv_cross_path=args.spirv_cross,
        fxc_path=args.fxc,
        dxc_path=args.dxc,
    )

    print(f"[OK] artifact index generated: {artifact_index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
