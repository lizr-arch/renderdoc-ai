import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Optional


def _first_existing_file(paths: Iterable[Path]) -> Optional[str]:
    for candidate in paths:
        if candidate.is_file():
            return str(candidate)
    return None


def _iter_windows_spirv_cross_candidates() -> Iterable[Path]:
    repo_root = Path(__file__).resolve().parents[3]

    # When RenderDoc is built/distributed, SPIRV tools may live under dist/.
    candidates = [
        repo_root / "dist" / "Release64" / "plugins" / "spirv" / "spirv-cross.exe",
        repo_root / "dist" / "Release32" / "plugins" / "spirv" / "spirv-cross.exe",
    ]

    # Common installation locations.
    for env_key in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        env_base = os.environ.get(env_key)
        if env_base:
            candidates.append(
                Path(env_base) / "RenderDoc" / "plugins" / "spirv" / "spirv-cross.exe"
            )

    return candidates


def _resolve_with_everything() -> Optional[str]:
    """Best-effort Windows search using Everything CLI (es.exe).

    We keep this optional and fast (short timeout) so it never blocks.
    """

    es_path = shutil.which("es.exe") or shutil.which("es")
    if not es_path:
        return None

    try:
        proc = subprocess.run(
            [es_path, "spirv-cross.exe"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    for line in proc.stdout.splitlines():
        candidate = Path(line.strip().strip('"'))
        if candidate.is_file() and candidate.name.lower() == "spirv-cross.exe":
            return str(candidate)

    return None


def _normalise_cli_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return str(Path(path.strip().strip('"')))


def resolve_spirv_cross_path(cli_path: Optional[str]) -> Optional[str]:
    # Explicit user-provided path always wins.
    for explicit_path in (
        _normalise_cli_path(cli_path),
        _normalise_cli_path(os.environ.get("SPIRV_CROSS")),
        _normalise_cli_path(os.environ.get("SPIRV_CROSS_PATH")),
    ):
        if explicit_path:
            return explicit_path

    # PATH-based discovery.
    for tool_name in ("spirv-cross", "spirv-cross.exe"):
        resolved = shutil.which(tool_name)
        if resolved:
            return resolved

    # Windows-only fallbacks.
    if os.name == "nt":
        from_known_locations = _first_existing_file(_iter_windows_spirv_cross_candidates())
        if from_known_locations:
            return from_known_locations

        from_everything = _resolve_with_everything()
        if from_everything:
            return from_everything

    return None


def require_spirv_cross(api: str, path: Optional[str]) -> None:
    if api == "vulkan" and not path:
        raise SystemExit("vulkan requires --spirv-cross or SPIRV_CROSS env var")


def run_spirv_cross(spirv_cross_path: str, spirv_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".spv") as handle:
        handle.write(spirv_bytes)
        tmp_path = handle.name
    try:
        proc = subprocess.run(
            [spirv_cross_path, tmp_path, "--hlsl", "--shader-model", "50"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "spirv-cross failed")
        return proc.stdout
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
