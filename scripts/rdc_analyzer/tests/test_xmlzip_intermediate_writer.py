import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_write_intermediate_full_outputs(tmp_path):
    try:
        from xmlzip_event_extractor import EventState, BufferBinding, write_intermediate
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    state = EventState(
        index_buffer=BufferBinding(resource_id=20, byte_offset=0, byte_size=12),
        vertex_buffers=[BufferBinding(resource_id=10, byte_offset=0, byte_size=16)],
        textures=[{"texture_id": 42, "path": "tex_42.bin"}],
        shaders=[{"stage": "vs", "path": "vs.bin"}],
    )

    write_intermediate(
        out_dir=str(tmp_path),
        state=state,
        buffers={},
        shaders={},
        textures={},
    )

    assert (tmp_path / "intermediate" / "materials" / "material.json").exists()
    assert (tmp_path / "intermediate" / "shaders" / "vs.json").exists()
    assert (tmp_path / "intermediate" / "textures" / "tex_42.bin").exists()
