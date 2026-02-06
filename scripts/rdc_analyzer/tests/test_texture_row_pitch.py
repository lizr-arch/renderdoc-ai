from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "exporters" / "texture_batch_exporter.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("texture_batch_exporter", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tighten_rows_by_pitch_rgba8() -> None:
    width = 2
    height = 2
    fmt = "DXGI_FORMAT_R8G8B8A8_UNORM"
    row_pitch = 12  # 8 bytes data + 4 bytes padding

    row0 = bytes([1, 2, 3, 4, 5, 6, 7, 8])
    row1 = bytes([9, 10, 11, 12, 13, 14, 15, 16])
    pad = bytes([0xFF, 0xEE, 0xDD, 0xCC])

    raw = row0 + pad + row1 + pad
    expected = row0 + row1

    module = _load_module()
    assert hasattr(module, "tighten_rows_by_pitch")
    assert module.tighten_rows_by_pitch(raw, width, height, row_pitch, fmt) == expected
