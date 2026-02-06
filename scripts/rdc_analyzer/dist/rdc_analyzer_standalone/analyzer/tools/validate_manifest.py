"""
Manifest Validation Tool

Usage:
  py -3 validate_manifest.py report_manifest.json
"""
import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: py -3 validate_manifest.py <manifest.json>")
        return 2

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    coverage = data.get("coverage", 0.0)
    print(f"coverage={coverage:.2f}")

    if coverage < 0.90:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
