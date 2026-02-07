import argparse
import json
from pathlib import Path

from export_event_import_bundle import export_event_import_bundle


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

    success_count = len([item for item in results if item.get("status") == "ok"])
    failed_count = len(results) - success_count

    return {
        "schema_version": "1.0",
        "root": str(intermediate_root),
        "out": str(out_root),
        "events_total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
    }


def _write_summary(summary: dict, summary_path: Path):
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Batch export import_bundle for multiple event_<id>/intermediate directories"
    )
    parser.add_argument("--root", required=True, help="Root directory containing event_<id>/intermediate")
    parser.add_argument("--out", required=True, help="Output root directory")
    parser.add_argument(
        "--events",
        required=False,
        help="Optional event ids, comma/space separated (e.g. 100,101,102)",
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

    root = Path(args.root)
    out = Path(args.out)

    event_ids = _parse_events_arg(args.events) if args.events else discover_event_ids(root)
    if not event_ids:
        raise ValueError("no event ids found. Provide --events or ensure root has event_<id>/intermediate")

    summary = run_batch(
        intermediate_root=root,
        out_root=out,
        event_ids=event_ids,
        rgba_manifest=args.rgba_manifest,
        fail_fast=bool(args.fail_fast),
    )

    summary_path = Path(args.summary) if args.summary else out / "batch_import_bundle_summary.json"
    _write_summary(summary, summary_path)

    print(
        f"[OK] batch done: total={summary['events_total']} success={summary['success_count']} "
        f"failed={summary['failed_count']} summary={summary_path}"
    )

    return 0 if summary["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
