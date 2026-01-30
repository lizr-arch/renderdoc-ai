import re
import sys


def parse_exports(lines):
    exports = []
    in_table = False
    for line in lines:
        if "ordinal" in line and "name" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip():
            if exports:
                break
            continue
        if not re.match(r"^\s*\d+", line):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[3]
        if name == "[NONAME]":
            continue
        exports.append(name)
    return exports


def main():
    if len(sys.argv) != 3:
        print("Usage: make_def.py <dumpbin_exports.txt> <out.def>")
        return 1
    src = sys.argv[1]
    out = sys.argv[2]
    with open(src, "r") as fh:
        lines = fh.readlines()
    exports = parse_exports(lines)
    if not exports:
        print("No exports found in dumpbin output.")
        return 2
    with open(out, "w") as fh:
        fh.write("LIBRARY python27.dll\n")
        fh.write("EXPORTS\n")
        for name in exports:
            fh.write("  %s\n" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
