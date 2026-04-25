from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TOOLS_DIR = Path(__file__).resolve().parents[1]
MCP_DIR = TOOLS_DIR / "mcp"

def _prepare_mcp_provider_imports() -> None:
    mcp_dir = str(MCP_DIR)
    if mcp_dir in sys.path:
        sys.path.remove(mcp_dir)
    sys.path.insert(0, mcp_dir)

    providers_module = sys.modules.get("providers")
    module_file = Path(str(getattr(providers_module, "__file__", ""))).resolve(strict=False)
    if providers_module is not None and MCP_DIR.resolve(strict=False) not in module_file.parents:
        for name in list(sys.modules):
            if name == "providers" or name.startswith("providers."):
                del sys.modules[name]


_prepare_mcp_provider_imports()

from providers import ProviderContext, SidecarLoadError, build_default_registry, load_sidecar  # type: ignore
from providers.sidecar_loader import DEFAULT_MAX_BYTES  # type: ignore


VALIDATOR_SCHEMA_VERSION = "eap-validator.v1"


def validate_sidecar(
    path: str,
    *,
    allowlist_dirs: Iterable[str] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    try:
        payload = load_sidecar(path, allowlist_dirs=allowlist_dirs, max_bytes=max_bytes)
    except SidecarLoadError as exc:
        return _error_result(exc)

    return {
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "ok": True,
        "sidecar": _summarize_sidecar(payload, path),
        "error": None,
    }


def format_human_summary(result: Dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {}) or {}
        lines = [
            f"ERROR: {error.get('code', 'unknown')}",
            f"message: {error.get('message', '')}",
        ]
        path = error.get("path")
        if path:
            lines.append(f"path: {path}")
        return "\n".join(lines)

    sidecar = result.get("sidecar", {}) or {}
    counts = sidecar.get("counts", {}) or {}
    nonzero_counts = [f"{name}={value}" for name, value in counts.items() if value]
    if not nonzero_counts:
        nonzero_counts = ["none"]

    capabilities = sidecar.get("capabilities", []) or []
    capability_text = ", ".join(str(name) for name in capabilities) if capabilities else "none"
    path_name = Path(str(sidecar.get("path", "sidecar"))).name
    return "\n".join(
        [
            f"OK: {path_name}",
            f"capture_id: {sidecar.get('capture_id') or 'unknown'}",
            f"schema: {sidecar.get('schema_name') or 'unknown'} v{sidecar.get('schema_version')}",
            f"counts: {', '.join(nonzero_counts)}",
            f"capabilities: {capability_text}",
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        result = validate_sidecar(
            args.path,
            allowlist_dirs=args.allowlist_dir or [],
            max_bytes=args.max_bytes,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(format_human_summary(result))
        return 0 if result.get("ok") else 2
    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate one explicit Engine Annotation Protocol .rmeta.json sidecar.",
    )
    subparsers = parser.add_subparsers(dest="command")
    validate = subparsers.add_parser("validate", help="validate an explicit .rmeta.json sidecar")
    validate.add_argument("path", help="path to a .rmeta.json sidecar")
    validate.add_argument(
        "--allowlist-dir",
        action="append",
        default=[],
        help="optional allowed directory root; repeat to allow multiple roots",
    )
    validate.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"maximum sidecar size in bytes, default {DEFAULT_MAX_BYTES}",
    )
    validate.add_argument("--json", action="store_true", help="emit deterministic machine-readable JSON")
    return parser


def _summarize_sidecar(payload: Dict[str, Any], path: str) -> Dict[str, Any]:
    schema = payload.get("schema", {}) if isinstance(payload.get("schema"), dict) else {}
    capture = payload.get("capture", {}) if isinstance(payload.get("capture"), dict) else {}
    availability = build_default_registry().data_availability(ProviderContext(eap_sidecar=payload)).as_dict()
    capability_rows = availability["providers"]["eap_sidecar"]["capabilities"]
    return {
        "path": str(Path(path).expanduser().resolve(strict=False)),
        "schema_name": schema.get("name"),
        "schema_version": schema.get("version"),
        "capture_id": capture.get("id") or availability.get("capture_id"),
        "counts": _count_sections(payload),
        "capabilities": [str(row.get("name")) for row in capability_rows],
    }


def _count_sections(payload: Dict[str, Any]) -> Dict[str, int]:
    render_graph = payload.get("render_graph", {}) if isinstance(payload.get("render_graph"), dict) else {}
    rules = payload.get("rules", {}) if isinstance(payload.get("rules"), dict) else {}
    return {
        "render_graph_nodes": _list_count(render_graph.get("nodes")),
        "commands": _list_count(payload.get("commands")),
        "resources": _list_count(payload.get("resources")),
        "assets": _list_count(payload.get("assets")),
        "materials": _list_count(payload.get("materials")),
        "shaders": _list_count(payload.get("shaders")),
        "pipelines": _list_count(payload.get("pipelines")),
        "rule_results": _list_count(rules.get("results")),
    }


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _error_result(exc: SidecarLoadError) -> Dict[str, Any]:
    return {
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "ok": False,
        "sidecar": None,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "path": exc.path,
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
