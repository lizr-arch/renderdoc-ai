import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rdc", required=True)
    parser.add_argument("--event", type=int, required=True)
    parser.add_argument("--api", required=True, choices=["d3d11", "vulkan"])
    parser.add_argument("--out", required=True)
    parser.parse_args()
    return 0


if __name__ == "__main__":
    sys.exit(main())
