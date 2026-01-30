import os
import shutil
from typing import Optional


def resolve_spirv_cross_path(cli_path: Optional[str]) -> Optional[str]:
    if cli_path:
        return cli_path
    env_path = os.environ.get("SPIRV_CROSS")
    if env_path:
        return env_path
    return shutil.which("spirv-cross")
