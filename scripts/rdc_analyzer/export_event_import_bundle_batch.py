import argparse
import json
from pathlib import Path

from export_event_import_bundle import _extract_then_export, export_event_import_bundle


_SCRIPT_DIR = Path(__file__).resolve().parent
_SCHEMA_DIR = _SCRIPT_DIR / "schema"


def _to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _assert_type(value, expected, path="root"):
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object")
        return
    if expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path}: expected array")
        return
    if expected == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected string")
        return
    if expected == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{path}: expected integer")
        return
    if expected == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{path}: expected number")
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{path}: expected boolean")
        return
    if expected == "null":
        if value is not None:
            raise ValueError(f"{path}: expected null")
        return
    raise ValueError(f"{path}: unsupported schema type {expected!r}")


def _validate_schema(schema, data, path="root"):
    expected_type = schema.get("type")
    if expected_type:
        if isinstance(expected_type, list):
            matched = False
            last_error = None
            for type_name in expected_type:
                try:
                    _assert_type(data, type_name, path)
                    matched = True
                    break
                except ValueError as exc:
                    last_error = exc
            if not matched:
                if last_error is not None:
                    raise last_error
                raise ValueError(f"{path}: no matching type in {expected_type!r}")
        else:
            _assert_type(data, expected_type, path)

    if "enum" in schema and data not in schema["enum"]:
        raise ValueError(f"{path}: value not in enum")

    if expected_type == "object":
        for required_key in schema.get("required", []):
            if required_key not in data:
                raise ValueError(f"{path}: missing required field {required_key}")
        for key, subschema in schema.get("properties", {}).items():
            if key in data:
                _validate_schema(subschema, data[key], f"{path}.{key}")

    if expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(data):
                _validate_schema(item_schema, item, f"{path}[{index}]")


def _validate_summary_payload(summary_payload: dict):
    schema_path = _SCHEMA_DIR / "batch_import_bundle_summary.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _validate_schema(schema, summary_payload)


def _parse_events_arg(events_arg: str):
    if not events_arg:
        return []

    event_ids = []
    for token in events_arg.replace(",", " ").split():
        if not token:
            continue
        if not token.isdigit():
            raise ValueError(f"invalid event id: {token}")
        event_ids.append(int(token))

    deduped = []
    seen = set()
    for event_id in event_ids:
        if event_id in seen:
            continue
        seen.add(event_id)
        deduped.append(event_id)
    return deduped


def _parse_source_kinds_arg(value: str | None):
    if not value:
        return set()

    out = []
    for token in str(value).replace(";", ",").split(","):
        item = token.strip()
        if item:
            out.append(item)
    return set(out)


def _to_optional_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 0:
            return False
        if value == 1:
            return True
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "y", "on"}:
            return True
        if token in {"0", "false", "no", "n", "off"}:
            return False
    return None


_MESH_HINT_KEYS = [
    "mesh_exportable",
    "mesh_compatible",
    "has_vertex_binding",
    "has_index_binding",
    "vertex_offset_zero",
    "first_index_within_hint",
    "vertex_layout_has_position",
    "has_position_semantic",
    "has_position",
]


def _mesh_hint(scan_item: dict):
    flags = []
    for key in _MESH_HINT_KEYS:
        if key not in scan_item:
            continue
        value = _to_optional_bool(scan_item.get(key))
        if value is not None:
            flags.append(value)

    if not flags:
        return "unknown"
    if all(flags):
        return "compatible"
    return "incompatible"


def _mesh_likely_score(scan_item: dict):
    score = 0

    index_count = _to_int(scan_item.get("index_count"), default=0)
    if index_count > 0:
        score += 2

    vertex_offset = _to_int(scan_item.get("vertex_offset"), default=0)
    if vertex_offset == 0:
        score += 3

    first_index = _to_int(scan_item.get("first_index"), default=0)
    if first_index <= 2048:
        score += 2
    elif first_index <= 8192:
        score += 1

    pipeline = _to_int(scan_item.get("pipeline"), default=0)
    if pipeline > 0:
        score += 1

    shader_stages = [str(stage).strip().lower() for stage in (scan_item.get("shader_stages") or [])]
    if "vs" in shader_stages:
        score += 1
    if "ps" in shader_stages:
        score += 1

    return score


def _select_events_from_scan(
    scan_path: Path,
    top_textured: int,
    min_textures: int,
    scan_rank: str = "mesh_likely",
):
    payload = json.loads(scan_path.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise ValueError(f"invalid scan payload: {scan_path}")

    selected = []
    for item in events:
        if not isinstance(item, dict):
            continue
        try:
            event_id = int(item.get("event_id"))
        except (TypeError, ValueError):
            continue

        texture_count = _to_int(item.get("texture_count"), default=0)
        if texture_count < int(min_textures):
            continue

        mesh_hint = _mesh_hint(item)
        mesh_likely_score = _mesh_likely_score(item)
        mesh_hint_rank = {"compatible": 2, "unknown": 1, "incompatible": 0}.get(mesh_hint, 1)

        selected_row = {
            "event_id": event_id,
            "texture_count": texture_count,
            "index_count": _to_int(item.get("index_count"), default=0),
            "pipeline": _to_int(item.get("pipeline"), default=0),
            "first_index": _to_int(item.get("first_index"), default=0),
            "vertex_offset": _to_int(item.get("vertex_offset"), default=0),
            "mesh_hint": mesh_hint,
            "mesh_likely_score": mesh_likely_score,
            "_mesh_hint_rank": mesh_hint_rank,
        }

        for mesh_key in _MESH_HINT_KEYS:
            mesh_value = _to_optional_bool(item.get(mesh_key))
            if mesh_value is not None:
                selected_row[mesh_key] = mesh_value

        selected.append(selected_row)

    ranking = str(scan_rank or "mesh_likely").strip().lower()
    if ranking == "mesh_likely":
        selected.sort(
            key=lambda row: (
                -int(row.get("_mesh_hint_rank", 1)),
                -int(row.get("mesh_likely_score", 0)),
                -int(row.get("texture_count", 0)),
                -int(row.get("index_count", 0)),
                abs(int(row.get("vertex_offset", 0))),
                int(row.get("first_index", 0)),
                int(row.get("event_id", 0)),
            )
        )
    else:
        selected.sort(key=lambda row: (-int(row.get("texture_count", 0)), int(row.get("event_id", 0))))

    for row in selected:
        row.pop("_mesh_hint_rank", None)

    if int(top_textured) > 0:
        selected = selected[: int(top_textured)]

    event_ids = [int(row["event_id"]) for row in selected]
    return event_ids, selected


def discover_event_ids(intermediate_root: Path):
    if not intermediate_root.exists():
        return []

    event_ids = []
    for child in sorted(intermediate_root.iterdir()):
        if not child.is_dir() or not child.name.startswith("event_"):
            continue

        suffix = child.name.split("_", 1)[1]
        if not suffix.isdigit():
            continue

        if (child / "intermediate").exists():
            event_ids.append(int(suffix))

    return event_ids


def _normalize_event_ids(values):
    if not isinstance(values, list):
        return []

    normalized = []
    seen = set()
    for value in values:
        try:
            event_id = int(value)
        except (TypeError, ValueError):
            continue
        if event_id in seen:
            continue
        seen.add(event_id)
        normalized.append(event_id)
    return normalized


def _failed_event_ids_from_summary(summary_payload: dict):
    explicit = _normalize_event_ids(summary_payload.get("failed_event_ids"))
    if explicit:
        return explicit

    derived = []
    seen = set()
    for item in summary_payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if status == "ok":
            continue
        try:
            event_id = int(item.get("event_id"))
        except (TypeError, ValueError):
            continue
        if event_id in seen:
            continue
        seen.add(event_id)
        derived.append(event_id)
    return derived


def _build_retry_command(
    root: Path,
    out: Path,
    failed_event_ids: list[int],
    rgba_manifest: str | None = None,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
    capture_xml: Path | None = None,
    capture_zip: Path | None = None,
    vertex_stride: int = 0,
):
    if not failed_event_ids:
        return ""

    events_arg = ",".join(str(event_id) for event_id in failed_event_ids)
    if capture_xml is not None and capture_zip is not None:
        command = (
            "py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py "
            f"--xml \"{capture_xml}\" --zip \"{capture_zip}\" --out \"{out}\" --events \"{events_arg}\""
        )
        if int(vertex_stride) > 0:
            command += f" --vertex-stride {int(vertex_stride)}"
    else:
        command = (
            "py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py "
            f"--root \"{root}\" --out \"{out}\" --events \"{events_arg}\""
        )

    if rgba_manifest:
        command += f" --rgba-manifest \"{rgba_manifest}\""

    mode = str(texture_mode or "auto").strip().lower()
    if mode and mode != "auto":
        command += f" --texture-mode \"{mode}\""

    kinds = sorted(raw_source_kinds or set())
    if kinds:
        command += f" --raw-source-kinds \"{','.join(kinds)}\""

    return command


_MESH_INCOMPATIBLE_ERROR_MARKERS = [
    "mesh.json missing vertex_layout/vertex_count/index_count",
    "vertex_layout missing POSITION",
    "has no vertex buffer binding",
    "has no index buffer binding",
]


def _is_mesh_incompatible_error(message: str):
    text = str(message or "")
    if not text:
        return False
    for marker in _MESH_INCOMPATIBLE_ERROR_MARKERS:
        if marker in text:
            return True
    return False


def _mesh_skip_reason_code(message: str):
    text = str(message or "")
    if "mesh.json missing vertex_layout/vertex_count/index_count" in text:
        return "mesh_layout_incomplete"
    if "vertex_layout missing POSITION" in text:
        return "missing_position_semantic"
    if "has no vertex buffer binding" in text:
        return "missing_vertex_buffer_binding"
    if "has no index buffer binding" in text:
        return "missing_index_buffer_binding"
    return "mesh_incompatible_unknown"


def _build_skip_diagnostics(summary: dict, selection: dict | None = None):
    selection_map = {}
    if isinstance(selection, dict):
        for row in selection.get("selected") or []:
            if not isinstance(row, dict):
                continue
            try:
                event_id = int(row.get("event_id"))
            except (TypeError, ValueError):
                continue
            selection_map[event_id] = row

    diagnostics = []
    for item in summary.get("results") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "")
        if not status.startswith("skipped"):
            continue

        try:
            event_id = int(item.get("event_id"))
        except (TypeError, ValueError):
            continue

        error_text = str(item.get("error") or "")
        reason_code = str(item.get("skip_reason") or "").strip() or _mesh_skip_reason_code(error_text)

        row = selection_map.get(event_id, {})
        scan_hints = {}
        hint_keys = [
            "mesh_hint",
            "mesh_likely_score",
            "texture_count",
            "index_count",
            "first_index",
            "vertex_offset",
            "mesh_incompatible_reasons",
        ] + list(_MESH_HINT_KEYS)
        for key in hint_keys:
            if key in row:
                scan_hints[key] = row.get(key)

        diagnostic = {
            "event_id": event_id,
            "status": status,
            "reason_code": reason_code,
            "error": error_text,
        }
        if scan_hints:
            diagnostic["scan_hints"] = scan_hints

        diagnostics.append(diagnostic)

    return diagnostics


def _load_texture_status_counts(bundle_root: Path):
    materials_path = bundle_root / "materials" / "materials.json"
    payload = json.loads(materials_path.read_text(encoding="utf-8")) if materials_path.exists() else {}

    counts = {
        "decoded_rgba8_png": 0,
        "rgba_bytes_png": 0,
        "copied_image": 0,
        "raw_copy": 0,
        "missing_source": 0,
        "other": 0,
    }

    materials = payload.get("materials") if isinstance(payload, dict) else []
    for material in materials or []:
        if not isinstance(material, dict):
            continue
        for texture in material.get("textures") or []:
            if not isinstance(texture, dict):
                continue
            status = str(texture.get("status") or "")
            if status in counts:
                counts[status] += 1
            else:
                counts["other"] += 1

    counts["total"] = sum(value for key, value in counts.items() if key != "total")
    return counts


def run_batch(
    intermediate_root: Path,
    out_root: Path,
    event_ids: list[int],
    rgba_manifest: str | None = None,
    fail_fast: bool = False,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
):
    results = []

    for event_id in event_ids:
        intermediate_path = intermediate_root / f"event_{event_id}" / "intermediate"
        if not intermediate_path.exists():
            results.append(
                {
                    "event_id": int(event_id),
                    "status": "missing_intermediate",
                    "bundle_dir": "",
                    "error": f"missing directory: {intermediate_path}",
                }
            )
            if fail_fast:
                break
            continue

        try:
            bundle_root = export_event_import_bundle(
                intermediate_dir=str(intermediate_path),
                out_dir=str(out_root),
                event_id=int(event_id),
                rgba_manifest=rgba_manifest,
                texture_mode=texture_mode,
                raw_source_kinds=raw_source_kinds,
            )

            bundle_manifest_path = Path(bundle_root) / "bundle_manifest.json"
            bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8")) if bundle_manifest_path.exists() else {}
            stats = bundle_manifest.get("statistics") if isinstance(bundle_manifest, dict) else {}
            texture_status_counts = _load_texture_status_counts(Path(bundle_root))

            results.append(
                {
                    "event_id": int(event_id),
                    "status": "ok",
                    "bundle_dir": str(bundle_root),
                    "error": "",
                    "statistics": {
                        "vertex_count": _to_int((stats or {}).get("vertex_count"), default=0),
                        "index_count": _to_int((stats or {}).get("index_count"), default=0),
                        "triangle_count": _to_int((stats or {}).get("triangle_count"), default=0),
                        "shader_count": _to_int((stats or {}).get("shader_count"), default=0),
                        "texture_count": _to_int((stats or {}).get("texture_count"), default=0),
                        "decoded_texture_count": _to_int((stats or {}).get("decoded_texture_count"), default=0),
                    },
                    "texture_status_counts": texture_status_counts,
                }
            )
        except Exception as exc:  # pragma: no cover - exercised in tests
            results.append(
                {
                    "event_id": int(event_id),
                    "status": "error",
                    "bundle_dir": "",
                    "error": str(exc),
                }
            )
            if fail_fast:
                break

    failed_event_ids = [
        int(item["event_id"])
        for item in results
        if str(item.get("status") or "") != "ok"
    ]
    skipped_event_ids = []
    success_count = len([item for item in results if item.get("status") == "ok"])
    skipped_count = 0
    failed_count = len(failed_event_ids)

    texture_status_totals = {
        "decoded_rgba8_png": 0,
        "rgba_bytes_png": 0,
        "copied_image": 0,
        "raw_copy": 0,
        "missing_source": 0,
        "other": 0,
        "total": 0,
    }
    for item in results:
        counts = item.get("texture_status_counts") if isinstance(item, dict) else None
        if not isinstance(counts, dict):
            continue
        for key in texture_status_totals.keys():
            texture_status_totals[key] += _to_int(counts.get(key), default=0)

    return {
        "schema_version": "1.0",
        "schema_path": "schema/batch_import_bundle_summary.schema.json",
        "root": str(intermediate_root),
        "out": str(out_root),
        "events_total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "failed_event_ids": failed_event_ids,
        "skipped_event_ids": skipped_event_ids,
        "skipped_count": skipped_count,
        "retry_events_arg": ",".join(str(event_id) for event_id in failed_event_ids),
        "retry_command": _build_retry_command(
            root=intermediate_root,
            out=out_root,
            failed_event_ids=failed_event_ids,
            rgba_manifest=rgba_manifest,
            texture_mode=texture_mode,
            raw_source_kinds=raw_source_kinds,
        ),
        "options": {
            "texture_mode": str(texture_mode or "auto").strip().lower() or "auto",
            "raw_source_kinds": sorted(raw_source_kinds or set()),
            "skip_mesh_incompatible": False,
        },
        "texture_status_totals": texture_status_totals,
        "results": results,
    }


def run_batch_from_capture(
    capture_xml: Path,
    capture_zip: Path,
    out_root: Path,
    event_ids: list[int],
    vertex_stride: int = 0,
    rgba_manifest: str | None = None,
    fail_fast: bool = False,
    texture_mode: str = "auto",
    raw_source_kinds: set[str] | None = None,
    skip_mesh_incompatible: bool = True,
):
    results = []

    for event_id in event_ids:
        try:
            bundle_root = _extract_then_export(
                xml_path=str(capture_xml),
                zip_path=str(capture_zip),
                event_id=int(event_id),
                out_dir=str(out_root),
                vertex_stride=int(vertex_stride),
                rgba_manifest=rgba_manifest,
                texture_mode=texture_mode,
                raw_source_kinds=raw_source_kinds,
            )

            bundle_manifest_path = Path(bundle_root) / "bundle_manifest.json"
            bundle_manifest = json.loads(bundle_manifest_path.read_text(encoding="utf-8")) if bundle_manifest_path.exists() else {}
            stats = bundle_manifest.get("statistics") if isinstance(bundle_manifest, dict) else {}
            texture_status_counts = _load_texture_status_counts(Path(bundle_root))

            results.append(
                {
                    "event_id": int(event_id),
                    "status": "ok",
                    "bundle_dir": str(bundle_root),
                    "error": "",
                    "statistics": {
                        "vertex_count": _to_int((stats or {}).get("vertex_count"), default=0),
                        "index_count": _to_int((stats or {}).get("index_count"), default=0),
                        "triangle_count": _to_int((stats or {}).get("triangle_count"), default=0),
                        "shader_count": _to_int((stats or {}).get("shader_count"), default=0),
                        "texture_count": _to_int((stats or {}).get("texture_count"), default=0),
                        "decoded_texture_count": _to_int((stats or {}).get("decoded_texture_count"), default=0),
                    },
                    "texture_status_counts": texture_status_counts,
                }
            )
        except Exception as exc:  # pragma: no cover - exercised in tests
            error_text = str(exc)
            status = "error"
            skip_reason = ""
            if skip_mesh_incompatible and _is_mesh_incompatible_error(error_text):
                status = "skipped_mesh_incompatible"
                skip_reason = _mesh_skip_reason_code(error_text)

            row = {
                "event_id": int(event_id),
                "status": status,
                "bundle_dir": "",
                "error": error_text,
            }
            if skip_reason:
                row["skip_reason"] = skip_reason

            results.append(row)
            if fail_fast and status == "error":
                break

    failed_event_ids = [
        int(item["event_id"])
        for item in results
        if str(item.get("status") or "") == "error"
    ]
    skipped_event_ids = [
        int(item["event_id"])
        for item in results
        if str(item.get("status") or "").startswith("skipped")
    ]
    success_count = len([item for item in results if item.get("status") == "ok"])
    skipped_count = len(skipped_event_ids)
    failed_count = len(failed_event_ids)

    texture_status_totals = {
        "decoded_rgba8_png": 0,
        "rgba_bytes_png": 0,
        "copied_image": 0,
        "raw_copy": 0,
        "missing_source": 0,
        "other": 0,
        "total": 0,
    }
    for item in results:
        counts = item.get("texture_status_counts") if isinstance(item, dict) else None
        if not isinstance(counts, dict):
            continue
        for key in texture_status_totals.keys():
            texture_status_totals[key] += _to_int(counts.get(key), default=0)

    return {
        "schema_version": "1.0",
        "schema_path": "schema/batch_import_bundle_summary.schema.json",
        "root": str(capture_xml.parent),
        "out": str(out_root),
        "events_total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "failed_event_ids": failed_event_ids,
        "skipped_event_ids": skipped_event_ids,
        "skipped_count": skipped_count,
        "retry_events_arg": ",".join(str(event_id) for event_id in failed_event_ids),
        "retry_command": _build_retry_command(
            root=capture_xml.parent,
            out=out_root,
            failed_event_ids=failed_event_ids,
            rgba_manifest=rgba_manifest,
            texture_mode=texture_mode,
            raw_source_kinds=raw_source_kinds,
            capture_xml=capture_xml,
            capture_zip=capture_zip,
            vertex_stride=int(vertex_stride),
        ),
        "inputs": {
            "mode": "capture_zip",
            "xml": str(capture_xml),
            "zip": str(capture_zip),
            "vertex_stride": int(vertex_stride),
        },
        "options": {
            "texture_mode": str(texture_mode or "auto").strip().lower() or "auto",
            "raw_source_kinds": sorted(raw_source_kinds or set()),
            "skip_mesh_incompatible": bool(skip_mesh_incompatible),
        },
        "texture_status_totals": texture_status_totals,
        "results": results,
    }


def _write_summary(summary: dict, summary_path: Path):
    _validate_summary_payload(summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _write_retry_artifacts(summary: dict, out_root: Path):
    failed_ids = list(summary.get("failed_event_ids") or [])
    if not failed_ids:
        return {}

    out_root.mkdir(parents=True, exist_ok=True)

    failed_path = out_root / "batch_import_bundle_failed_events.txt"
    failed_path.write_text("\n".join(str(event_id) for event_id in failed_ids) + "\n", encoding="utf-8")

    command_path = out_root / "batch_import_bundle_retry_command.txt"
    command_path.write_text(str(summary.get("retry_command") or "") + "\n", encoding="utf-8")

    return {
        "failed_events": str(failed_path),
        "retry_command": str(command_path),
    }



def _write_skip_artifacts(summary: dict, out_root: Path):
    diagnostics = list(summary.get("skip_diagnostics") or [])
    if not diagnostics:
        return {}

    out_root.mkdir(parents=True, exist_ok=True)

    diag_path = out_root / "batch_import_bundle_skip_diagnostics.json"
    diag_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

    return {
        "skip_diagnostics": str(diag_path),
    }


def _load_summary(path_value: str):
    path = Path(path_value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid summary format: {path}")
    return path, payload


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Batch export import_bundle for event_<id>/intermediate roots "
            "or directly from capture.zip.xml + capture.zip"
        )
    )
    parser.add_argument(
        "--root",
        required=False,
        help="Root directory containing event_<id>/intermediate; optional with --from-summary",
    )
    parser.add_argument("--xml", required=False, help="Path to capture.zip.xml (direct extract mode)")
    parser.add_argument("--zip", required=False, help="Path to capture.zip (direct extract mode)")
    parser.add_argument(
        "--vertex-stride",
        required=False,
        type=int,
        default=0,
        help="Optional vertex stride hint for direct extract mode",
    )
    parser.add_argument(
        "--out",
        required=False,
        help="Output root directory; optional with --from-summary (falls back to summary out)",
    )
    parser.add_argument(
        "--events",
        required=False,
        help="Optional event ids, comma/space separated (e.g. 100,101,102)",
    )
    parser.add_argument(
        "--events-from-scan",
        required=False,
        help="Optional scan JSON containing events[] with event_id/texture_count",
    )
    parser.add_argument(
        "--top-textured",
        required=False,
        type=int,
        default=0,
        help="When used with --events-from-scan, keep top-N by texture_count (0 means all)",
    )
    parser.add_argument(
        "--min-textures",
        required=False,
        type=int,
        default=1,
        help="When used with --events-from-scan, keep events with texture_count >= this value",
    )
    parser.add_argument(
        "--scan-rank",
        required=False,
        choices=["mesh_likely", "texture_count"],
        default="mesh_likely",
        help="Ranking policy for --events-from-scan (default: mesh_likely)",
    )
    parser.add_argument(
        "--from-summary",
        required=False,
        help="Retry from an existing batch summary JSON (uses failed_event_ids by default)",
    )
    parser.add_argument(
        "--rgba-manifest",
        required=False,
        help="Optional shared rgba manifest path (single file for all events)",
    )
    parser.add_argument(
        "--texture-mode",
        required=False,
        choices=["auto", "decoded", "raw"],
        default="auto",
        help="Texture export mode for each event",
    )
    parser.add_argument(
        "--raw-source-kinds",
        required=False,
        default="",
        help="Comma-separated source_kind values that force raw export when --texture-mode=auto",
    )
    parser.add_argument(
        "--summary",
        required=False,
        help="Optional summary output path (default: <out>/batch_import_bundle_summary.json)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at first failure",
    )
    parser.add_argument(
        "--strict-mesh",
        action="store_true",
        help="Treat mesh-incompatible events as hard errors (default is skip)",
    )
    args = parser.parse_args(argv)

    source_summary_path = None
    source_summary_payload = None
    if args.from_summary:
        source_summary_path, source_summary_payload = _load_summary(args.from_summary)

    capture_xml = None
    capture_zip = None
    capture_vertex_stride = int(args.vertex_stride or 0)

    if args.xml or args.zip:
        if not args.xml or not args.zip:
            raise ValueError("--xml and --zip must be provided together")
        capture_xml = Path(args.xml)
        capture_zip = Path(args.zip)
    elif source_summary_payload is not None:
        inputs = source_summary_payload.get("inputs")
        if isinstance(inputs, dict) and str(inputs.get("mode") or "") == "capture_zip":
            xml_value = inputs.get("xml")
            zip_value = inputs.get("zip")
            if xml_value and zip_value:
                capture_xml = Path(str(xml_value))
                capture_zip = Path(str(zip_value))
                if capture_vertex_stride <= 0:
                    capture_vertex_stride = _to_int(inputs.get("vertex_stride"), default=0)

    use_capture = capture_xml is not None and capture_zip is not None

    if args.out:
        out = Path(args.out)
    elif source_summary_payload and source_summary_payload.get("out"):
        out = Path(str(source_summary_payload.get("out")))
    else:
        raise ValueError("--out is required unless --from-summary provides out")

    if use_capture:
        root = capture_xml.parent
    else:
        if args.root:
            root = Path(args.root)
        elif source_summary_payload and source_summary_payload.get("root"):
            root = Path(str(source_summary_payload.get("root")))
        else:
            raise ValueError("--root is required in intermediate mode unless --from-summary provides root")

    raw_source_kinds = _parse_source_kinds_arg(args.raw_source_kinds)

    selection = None
    if args.events:
        event_ids = _parse_events_arg(args.events)
    elif args.events_from_scan:
        scan_path = Path(args.events_from_scan)
        event_ids, selected_rows = _select_events_from_scan(
            scan_path=scan_path,
            top_textured=int(args.top_textured),
            min_textures=max(0, int(args.min_textures)),
            scan_rank=args.scan_rank,
        )
        selection = {
            "source": str(scan_path),
            "top_textured": int(args.top_textured),
            "min_textures": max(0, int(args.min_textures)),
            "scan_rank": str(args.scan_rank),
            "selected": selected_rows,
        }
    elif source_summary_payload is not None:
        event_ids = _failed_event_ids_from_summary(source_summary_payload)
    else:
        if use_capture:
            raise ValueError(
                "capture mode requires --events or --events-from-scan (or --from-summary with failed_event_ids)"
            )
        event_ids = discover_event_ids(root)

    if not event_ids:
        raise ValueError(
            "no event ids found. Provide --events, --events-from-scan, ensure root has "
            "event_<id>/intermediate, or provide --from-summary with failed_event_ids/results"
        )

    if use_capture:
        summary = run_batch_from_capture(
            capture_xml=capture_xml,
            capture_zip=capture_zip,
            out_root=out,
            event_ids=event_ids,
            vertex_stride=int(capture_vertex_stride),
            rgba_manifest=args.rgba_manifest,
            fail_fast=bool(args.fail_fast),
            texture_mode=args.texture_mode,
            raw_source_kinds=raw_source_kinds,
            skip_mesh_incompatible=not bool(args.strict_mesh),
        )
    else:
        summary = run_batch(
            intermediate_root=root,
            out_root=out,
            event_ids=event_ids,
            rgba_manifest=args.rgba_manifest,
            fail_fast=bool(args.fail_fast),
            texture_mode=args.texture_mode,
            raw_source_kinds=raw_source_kinds,
        )

    summary_options = summary.setdefault("options", {})
    summary_options["scan_rank"] = str(args.scan_rank or "mesh_likely").strip().lower() or "mesh_likely"

    if source_summary_path is not None:
        summary["source_summary"] = str(source_summary_path)
    if selection is not None:
        summary["selection"] = selection

    skip_diagnostics = _build_skip_diagnostics(summary, selection=selection)
    if skip_diagnostics:
        summary["skip_diagnostics"] = skip_diagnostics

    retry_files = _write_retry_artifacts(summary, out)
    if retry_files:
        summary["retry_files"] = retry_files

    skip_files = _write_skip_artifacts(summary, out)
    if skip_files:
        summary["skip_files"] = skip_files

    summary_path = Path(args.summary) if args.summary else out / "batch_import_bundle_summary.json"
    _write_summary(summary, summary_path)

    print(
        f"[OK] batch done: total={summary['events_total']} success={summary['success_count']} "
        f"skipped={summary.get('skipped_count', 0)} failed={summary['failed_count']} summary={summary_path}"
    )

    return 0 if summary["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
