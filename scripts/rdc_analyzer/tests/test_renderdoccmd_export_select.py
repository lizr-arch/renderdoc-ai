from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "exporters" / "renderdoccmd_exporter.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("renderdoccmd_exporter", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_textures_by_area() -> None:
    entries = [
        {"id": 1, "width": 2, "height": 2, "file": "a.png"},
        {"id": 2, "width": 8, "height": 8, "file": "b.png"},
        {"id": 3, "width": 4, "height": 4, "file": "c.png"},
    ]
    module = _load_module()
    assert hasattr(module, "select_textures")
    selected = module.select_textures(entries, 2)
    assert [e["id"] for e in selected] == [2, 3]
