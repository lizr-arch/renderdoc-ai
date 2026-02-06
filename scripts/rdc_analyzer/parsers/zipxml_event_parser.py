from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass
class DrawEvent:
    event_id: int
    chunk_index: int
    name: str
    api: str


def _detect_api(root: ET.Element) -> str:
    driver = root.find(".//driver")
    if driver is None or driver.text is None:
        return "Unknown"
    return driver.text.strip() or "Unknown"


def iter_draw_events(xml_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    api = _detect_api(root)

    for chunk in root.findall(".//chunk"):
        name = chunk.get("name", "")
        if "Draw" not in name and "Dispatch" not in name:
            continue

        chunk_index = int(chunk.get("chunkIndex", "0"))
        yield DrawEvent(
            event_id=chunk_index,
            chunk_index=chunk_index,
            name=name,
            api=api,
        )
