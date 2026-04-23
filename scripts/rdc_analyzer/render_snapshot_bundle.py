from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.snapshot_template_renderer import SnapshotTemplateRenderer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a template.v1 HTML bundle directly from snapshot.v1.json."
    )
    parser.add_argument("snapshot", help="Path to snapshot.v1.json")
    parser.add_argument("-o", "--output-dir", required=True, help="Directory to write HTML bundle into")
    parser.add_argument(
        "--capture-name",
        default="",
        help="Optional capture name override. Defaults to snapshot meta.capture_name.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_path = Path(args.snapshot)
    output_dir = Path(args.output_dir)

    if not snapshot_path.exists():
        print(f"snapshot file not found: {snapshot_path}", file=sys.stderr)
        return 1

    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"failed to parse snapshot JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(snapshot, dict):
        print("snapshot payload must be a JSON object", file=sys.stderr)
        return 1

    renderer = SnapshotTemplateRenderer(output_dir=output_dir, capture_name=args.capture_name)
    outputs = renderer.render(snapshot)

    print("Rendered snapshot HTML bundle:")
    for key in ("index", "events", "textures", "shaders", "pipelines", "manifest"):
        path = outputs.get(key)
        if path:
            print(f"  - {Path(path).name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
