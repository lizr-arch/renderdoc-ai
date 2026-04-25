from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union

from .eap_sidecar_provider import looks_like_eap_sidecar


PathLike = Union[str, os.PathLike[str]]
DEFAULT_MAX_BYTES = 256 * 1024 * 1024


class SidecarLoadError(ValueError):
    def __init__(self, code: str, message: str, path: Optional[PathLike] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = str(path) if path is not None else None


def load_sidecar(
    path: PathLike,
    *,
    allowlist_dirs: Iterable[PathLike] = (),
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    resolved_path = _resolve_path(path)
    if not resolved_path.name.lower().endswith(".rmeta.json"):
        raise SidecarLoadError(
            "invalid_extension",
            "Sidecar path must end with .rmeta.json",
            resolved_path,
        )

    allowlist_roots = [_resolve_path(root) for root in allowlist_dirs]
    if allowlist_roots and not any(_is_inside(resolved_path, root) for root in allowlist_roots):
        raise SidecarLoadError(
            "not_allowed",
            "Sidecar path is outside the allowed directories",
            resolved_path,
        )

    if not resolved_path.exists():
        raise SidecarLoadError("not_found", "Sidecar file was not found", resolved_path)
    if not resolved_path.is_file():
        raise SidecarLoadError("not_file", "Sidecar path is not a file", resolved_path)

    try:
        byte_count = resolved_path.stat().st_size
    except OSError as exc:
        raise SidecarLoadError("stat_failed", str(exc), resolved_path) from exc
    if byte_count > max_bytes:
        raise SidecarLoadError(
            "file_too_large",
            f"Sidecar file is {byte_count} bytes, larger than the {max_bytes} byte limit",
            resolved_path,
        )

    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SidecarLoadError("invalid_json", "Sidecar file is not valid JSON", resolved_path) from exc
    except OSError as exc:
        raise SidecarLoadError("read_failed", str(exc), resolved_path) from exc

    if not isinstance(payload, dict):
        raise SidecarLoadError("invalid_payload", "Sidecar JSON root must be an object", resolved_path)
    if not looks_like_eap_sidecar(payload):
        raise SidecarLoadError("invalid_sidecar", "JSON object is not an EAP sidecar", resolved_path)
    return payload


def _resolve_path(path: PathLike) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
