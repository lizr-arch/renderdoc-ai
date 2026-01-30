import argparse
import os
import sys

EXPORTERS_DIR = os.path.join(os.path.dirname(__file__), "exporters")
sys.path.insert(0, os.path.abspath(EXPORTERS_DIR))

from spirv_cross_bridge import resolve_spirv_cross_path
from unity_exporter import export_unity_assets


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--rdc", required=True)
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--api", required=True, choices=["d3d11", "vulkan"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--spirv-cross", dest="spirv_cross")
    return parser.parse_args(argv)


def validate_args(args) -> None:
    if args.api == "vulkan" and resolve_spirv_cross_path(args.spirv_cross) is None:
        raise SystemExit("vulkan requires --spirv-cross or SPIRV_CROSS env var")


def main() -> int:
    args = parse_args()
    validate_args(args)

    try:
        export_unity_assets(args.rdc, args.event, args.api, args.out)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
