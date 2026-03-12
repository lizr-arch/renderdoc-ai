import json
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_write_intermediate_decodes_texture_and_manifest(tmp_path):
    try:
        from xmlzip_event_extractor import EventState, BufferBinding, write_intermediate
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    state = EventState(
        index_buffer=BufferBinding(resource_id=20, byte_offset=0, byte_size=12),
        vertex_buffers=[BufferBinding(resource_id=10, byte_offset=0, byte_size=16)],
        textures=[
            {
                "texture_id": 42,
                "path": "tex_42.bin",
                "format": "RGBA8",
                "width": 1,
                "height": 1,
                "zip_entry": "buffers/buffer12",
            }
        ],
        shaders=[],
    )

    write_intermediate(
        out_dir=str(tmp_path),
        state=state,
        buffers={},
        shaders={},
        textures={"tex_42.bin": b"\x01\x02\x03\x04"},
    )

    tex_path = tmp_path / "intermediate" / "textures" / "tex_42.bin"
    assert tex_path.exists()
    assert tex_path.read_bytes() == b"\x01\x02\x03\x04"

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    record = manifest["texture_decode"][0]
    assert record["zip_entry"] == "buffers/buffer12"
    assert record["decode_status"] == "ok"
