from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_MCP = REPO_ROOT / "tools" / "mcp"
if str(TOOLS_MCP) not in sys.path:
    sys.path.insert(0, str(TOOLS_MCP))

from snapshot_consumer import (  # type: ignore
    build_error_payload,
    classify_mcp_error,
    create_default_bridge,
    normalize_mcp_success,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one MCP query call and print JSON result.")
    parser.add_argument("--method", required=True, help="MCP method name")
    parser.add_argument(
        "--params",
        default="{}",
        help="JSON object params string, e.g. '{\"event_id\":101}'",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    try:
        params = json.loads(args.params)
        if not isinstance(params, dict):
            raise ValueError("params must be a JSON object")
    except Exception as exc:
        payload = build_error_payload(
            code="invalid_argument",
            message=f"Invalid --params: {exc}",
            method=args.method,
            params={},
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    try:
        bridge = create_default_bridge()
        result = bridge.call(args.method, params)
        payload = normalize_mcp_success(result, method=args.method, params=params)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        code = classify_mcp_error(str(exc))
        payload = build_error_payload(
            code=code,
            message=str(exc),
            method=args.method,
            params=params,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
