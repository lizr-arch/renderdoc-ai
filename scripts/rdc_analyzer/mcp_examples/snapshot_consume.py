from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_MCP = REPO_ROOT / "tools" / "mcp"
if str(TOOLS_MCP) not in sys.path:
    sys.path.insert(0, str(TOOLS_MCP))

from snapshot_consumer import analyze_snapshot  # type: ignore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consume snapshot.v1, detect gaps, and optionally run MCP supplement queries."
    )
    parser.add_argument("--snapshot", required=True, help="Path to snapshot.v1 JSON file")
    parser.add_argument("--execute", action="store_true", help="Execute MCP queries (default: dry-run)")
    parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum event count used for pipeline supplement planning (default: 5)",
    )
    parser.add_argument("--out-md", help="Optional output markdown path")
    parser.add_argument("--out-cmd", help="Optional output command list path")
    parser.add_argument("--out-json", help="Optional output analyzed JSON path")
    return parser.parse_args()


def _write_text(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _write_json(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = _parse_args()
    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        print(f"[ERROR] snapshot file not found: {snapshot_path}", file=sys.stderr)
        return 2

    with snapshot_path.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)

    result = analyze_snapshot(
        snapshot,
        execute=bool(args.execute),
        max_events=int(args.max_events),
    )

    markdown = str(result.get("markdown", ""))
    commands = result.get("commands", []) or []
    cmd_text = "\n".join(str(cmd) for cmd in commands).strip()
    if cmd_text:
        cmd_text += "\n"

    if args.out_md:
        _write_text(args.out_md, markdown)
    else:
        print(markdown)

    if args.out_cmd:
        _write_text(args.out_cmd, cmd_text)
    if args.out_json:
        _write_json(args.out_json, result)

    gaps = result.get("gaps", []) or []
    enrichment = result.get("enrichment", {}) or {}
    print(
        "[SUMMARY] gaps={gaps} queries={queries} execute={execute} status={status}".format(
            gaps=len(gaps),
            queries=len(commands),
            execute=bool(args.execute),
            status=enrichment.get("status", "unknown"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
