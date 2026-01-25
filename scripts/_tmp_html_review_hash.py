from pathlib import Path
import hashlib
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: _tmp_html_review_hash.py <dir>")
        return 2
    root = Path(sys.argv[1])
    pngs = sorted(root.glob("*.png"))
    if not pngs:
        print("No PNG files found.")
        return 1
    for p in pngs:
        data = p.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        print(f"{p.name} {h} {len(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
