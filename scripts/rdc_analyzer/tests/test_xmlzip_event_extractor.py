import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_extract_event_bindings_from_xml(tmp_path):
    try:
        from xmlzip_event_extractor import extract_event_state
    except ImportError as exc:
        pytest.fail(f"xmlzip_event_extractor missing: {exc}")

    xml_path = tmp_path / "sample.zip.xml"
    xml_path.write_text(
        """<root>
  <event id="100">
    <vertex_buffers>
      <vb resource_id="10" byte_offset="0" byte_size="16" />
      <vb resource_id="11" byte_offset="4" byte_size="20" />
    </vertex_buffers>
    <index_buffer resource_id="20" byte_offset="0" byte_size="12" />
  </event>
</root>
""",
        encoding="utf-8",
    )

    state = extract_event_state(str(xml_path), event_id=100)
    assert state.index_buffer is not None
    assert state.index_buffer.resource_id == 20
    assert len(state.vertex_buffers) == 2


def test_write_intermediate_outputs(tmp_path):
    from xmlzip_event_extractor import EventState, BufferBinding, write_intermediate

    state = EventState(
        index_buffer=BufferBinding(resource_id=20, byte_offset=0, byte_size=12),
        vertex_buffers=[BufferBinding(resource_id=10, byte_offset=0, byte_size=16)],
        textures=[],
        shaders=[],
    )

    write_intermediate(
        out_dir=str(tmp_path),
        state=state,
        buffers={},
        shaders={},
        textures={},
    )

    assert (tmp_path / "intermediate" / "mesh" / "mesh.json").exists()
