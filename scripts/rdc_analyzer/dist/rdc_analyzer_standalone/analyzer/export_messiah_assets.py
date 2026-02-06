import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
EXPORTERS_DIR = SCRIPT_DIR / "exporters"
sys.path.insert(0, str(EXPORTERS_DIR))

from messiah_exporter import export_messiah


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export Messiah assets from intermediate output")
    parser.add_argument("--intermediate", required=True, help="Intermediate directory")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--event", required=True, help="Event ID")
    args = parser.parse_args(argv)

    return export_messiah(args.intermediate, args.out, int(args.event))


if __name__ == "__main__":
    main()
