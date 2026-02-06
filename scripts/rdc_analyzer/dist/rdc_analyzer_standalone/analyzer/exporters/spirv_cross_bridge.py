import os
import shutil
import subprocess
import tempfile
from typing import Optional


def resolve_spirv_cross_path(cli_path: Optional[str]) -> Optional[str]:
    if cli_path:
        return cli_path
    env_path = os.environ.get("SPIRV_CROSS")
    if env_path:
        return env_path
    return shutil.which("spirv-cross")


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
