#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderDoc Python Shell helper for generating analysis.json with shader data.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def _ensure_scripts_path() -> None:
    if "__file__" not in globals():
        return
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def run(
    rdc_path: str,
    output_dir: str,
    output_name: str = "analysis.json",
    overwrite: bool = True,
) -> Path:
    """
    Run rdc_analyzer analysis inside RenderDoc Python Shell and export analysis.json.

    Args:
        rdc_path: Path to the RDC capture file.
        output_dir: Directory to place analysis output files.
        output_name: Target filename for analysis json (default: analysis.json).
        overwrite: Whether to overwrite existing output_name.
    """
    _ensure_scripts_path()
    from rdc_analyzer.main import analyze

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    analyze(rdc_path, output_dir=str(output_path), output_formats=["json"])

    json_files = sorted(
        output_path.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not json_files:
        raise FileNotFoundError("No JSON outputs were generated.")

    target = output_path / output_name
    if target.exists() and not overwrite:
        raise FileExistsError(f"Target already exists: {target}")

    shutil.copy2(json_files[0], target)
    print(f"[+] analysis.json ready: {target}")
    return target


__all__ = ["run"]
