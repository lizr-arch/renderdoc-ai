import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_iter_draw_events_from_chunk_xml(tmp_path):
    try:
        from parsers.zipxml_event_parser import iter_draw_events
    except ImportError as exc:
        pytest.fail(f"zipxml_event_parser missing: {exc}")

    xml_path = tmp_path / "sample.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header>
    <driver id="8">Vulkan</driver>
  </header>
  <chunks>
    <chunk id="1000" chunkIndex="10" name="vkCmdBindPipeline" />
    <chunk id="1085" chunkIndex="11" name="vkCmdDrawIndexed" />
    <chunk id="1090" chunkIndex="12" name="vkCmdDispatch" />
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )

    events = list(iter_draw_events(str(xml_path)))

    assert len(events) == 2
    assert events[0].event_id == 11
    assert events[0].name == "vkCmdDrawIndexed"
    assert events[0].api == "Vulkan"
    assert events[1].event_id == 12
    assert events[1].name == "vkCmdDispatch"
