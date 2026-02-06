"""renderdoccmd_exporter.py - helpers for renderdoccmd export output"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any


def load_textures_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("textures", [])


def select_textures(entries: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    ordered = sorted(
        entries,
        key=lambda e: (-(e.get("width", 0) * e.get("height", 0)), e.get("id", 0)),
    )
    return ordered[:limit]
