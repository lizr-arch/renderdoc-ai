#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Install the RDC Analyzer UI extension into the RenderDoc extensions directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Optional


def get_extensions_root(appdata: Optional[str] = None) -> Path:
    root = appdata or os.getenv("APPDATA")
    if not root:
        raise RuntimeError("APPDATA is not set; cannot locate extensions directory.")
    return Path(root) / "qrenderdoc" / "extensions"


def write_extension_config(dest_dir: Path, scripts_root: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    config_path = dest_dir / "extension_config.json"
    config = {"scripts_root": str(scripts_root)}
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


def install_extension(
    source_dir: Path,
    scripts_root: Path,
    dest_root: Optional[Path] = None,
    name: str = "rdc_analyzer",
) -> Path:
    dest_base = dest_root or get_extensions_root()
    dest_dir = dest_base / name
    dest_dir.mkdir(parents=True, exist_ok=True)

    if not (source_dir / "extension.json").exists():
        raise FileNotFoundError(f"Missing extension.json in {source_dir}")

    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
    write_extension_config(dest_dir, scripts_root)
    return dest_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install RDC Analyzer UI extension")
    default_source = Path(__file__).resolve().parents[1] / "ui_extension"
    default_scripts_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--source", default=str(default_source), help="Source extension dir")
    parser.add_argument(
        "--scripts-root",
        default=str(default_scripts_root),
        help="Root directory containing rdc_analyzer package",
    )
    parser.add_argument(
        "--dest-root",
        default=None,
        help="Override destination extensions root (optional)",
    )
    parser.add_argument("--name", default="rdc_analyzer", help="Extension package name")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    source_dir = Path(args.source).resolve()
    scripts_root = Path(args.scripts_root).resolve()
    dest_root = Path(args.dest_root).resolve() if args.dest_root else None
    dest = install_extension(
        source_dir=source_dir,
        scripts_root=scripts_root,
        dest_root=dest_root,
        name=args.name,
    )
    print(f"[+] Installed to: {dest}")


if __name__ == "__main__":
    main()
