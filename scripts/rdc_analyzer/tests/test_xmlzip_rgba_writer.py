import json
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_writer_outputs_rgba_and_shader_artifacts(tmp_path):
    try:
        from xmlzip_event_extractor import EventState, BufferBinding, write_intermediate
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    state = EventState(
        index_buffer=BufferBinding(resource_id=20, byte_offset=0, byte_size=12),
        vertex_buffers=[BufferBinding(resource_id=10, byte_offset=0, byte_size=16)],
        textures=[{"texture_id": 42, "path": "tex_42.bin", "format": "RGBA8"}],
        shaders=[{"stage": "vs", "path": "vs.bin", "disassembly": "vs.asm"}],
    )

    write_intermediate(
        out_dir=str(tmp_path),
        state=state,
        buffers={},
        shaders={"vs.bin": b"xx"},
        textures={"tex_42.bin": b"yy"},
    )

    assert (tmp_path / "intermediate" / "textures" / "tex_42.bin").exists()
    assert (tmp_path / "intermediate" / "shaders" / "vs.bin").exists()
    assert (tmp_path / "intermediate" / "shaders" / "vs.json").exists()

    shader_json = json.loads((tmp_path / "intermediate" / "shaders" / "vs.json").read_text(encoding="utf-8"))
    assert shader_json["shader"]["disassembly"] == "vs.asm"
