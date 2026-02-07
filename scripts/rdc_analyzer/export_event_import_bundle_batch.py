import argparse
import json
from pathlib import Path

from export_event_import_bundle import export_event_import_bundle


_SCRIPT_DIR = Path(__file__).resolve().parent
_SCHEMA_DIR = _SCRIPT_DIR / "schema"


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


def _build_retry_command(root: Path, out: Path, failed_event_ids: list[int], rgba_manifest: str | None = None):
    if not failed_event_ids:
        return ""

    events_arg = ",".join(str(event_id) for event_id in failed_event_ids)
    command = (
        "py -3 scripts/rdc_analyzer/export_event_import_bundle_batch.py "
        f"--root \"{root}\" --out \"{out}\" --events \"{events_arg}\""
    )
    if rgba_manifest:
        command += f" --rgba-manifest \"{rgba_manifest}\""
    return command


def run_batch(
    intermediate_root: Path,
    out_root: Path,
    event_ids: list[int],
    rgba_manifest: str | None = None,
    fail_fast: bool = False,
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
            )
            results.append(
                {
                    "event_id": int(event_id),
                    "status": "ok",
                    "bundle_dir": str(bundle_root),
                    "error": "",
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
    success_count = len([item for item in results if item.get("status") == "ok"])
    failed_count = len(results) - success_count

    return {
        "schema_version": "1.0",
        "schema_path": "schema/batch_import_bundle_summary.schema.json",
        "root": str(intermediate_root),
        "out": str(out_root),
        "events_total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "failed_event_ids": failed_event_ids,
        "retry_events_arg": ",".join(str(event_id) for event_id in failed_event_ids),
        "retry_command": _build_retry_command(
            root=intermediate_root,
            out=out_root,
            failed_event_ids=failed_event_ids,
            rgba_manifest=rgba_manifest,
        ),
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


def _load_summary(path_value: str):
    path = Path(path_value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid summary format: {path}")
    return path, payload


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Batch export import_bundle for multiple event_<id>/intermediate directories"
    )
    parser.add_argument(
        "--root",
        required=False,
        help="Root directory containing event_<id>/intermediate; optional with --from-summary",
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
        "--summary",
        required=False,
        help="Optional summary output path (default: <out>/batch_import_bundle_summary.json)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at first failure",
    )
    args = parser.parse_args(argv)

    source_summary_path = None
    source_summary_payload = None
    if args.from_summary:
        source_summary_path, source_summary_payload = _load_summary(args.from_summary)

    if args.root:
        root = Path(args.root)
    elif source_summary_payload and source_summary_payload.get("root"):
        root = Path(str(source_summary_payload.get("root")))
    else:
        raise ValueError("--root is required unless --from-summary provides root")

    if args.out:
        out = Path(args.out)
    elif source_summary_payload and source_summary_payload.get("out"):
        out = Path(str(source_summary_payload.get("out")))
    else:
        raise ValueError("--out is required unless --from-summary provides out")

    if args.events:
        event_ids = _parse_events_arg(args.events)
    elif source_summary_payload is not None:
        event_ids = _failed_event_ids_from_summary(source_summary_payload)
    else:
        event_ids = discover_event_ids(root)

    if not event_ids:
        raise ValueError(
            "no event ids found. Provide --events, ensure root has event_<id>/intermediate, "
            "or provide --from-summary with failed_event_ids/results"
        )

    summary = run_batch(
        intermediate_root=root,
        out_root=out,
        event_ids=event_ids,
        rgba_manifest=args.rgba_manifest,
        fail_fast=bool(args.fail_fast),
    )

    if source_summary_path is not None:
        summary["source_summary"] = str(source_summary_path)

    retry_files = _write_retry_artifacts(summary, out)
    if retry_files:
        summary["retry_files"] = retry_files

    summary_path = Path(args.summary) if args.summary else out / "batch_import_bundle_summary.json"
    _write_summary(summary, summary_path)

    print(
        f"[OK] batch done: total={summary['events_total']} success={summary['success_count']} "
        f"failed={summary['failed_count']} summary={summary_path}"
    )

    return 0 if summary["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
