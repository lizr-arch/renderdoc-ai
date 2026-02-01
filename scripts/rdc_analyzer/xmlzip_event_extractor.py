from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass
class BufferBinding:
    resource_id: int
    byte_offset: int
    byte_size: int


@dataclass
class EventState:
    index_buffer: BufferBinding | None
    vertex_buffers: list[BufferBinding]
    textures: list[dict]
    shaders: list[dict]


def _to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_buffer(elem):
    return BufferBinding(
        resource_id=_to_int(elem.get("resource_id")),
        byte_offset=_to_int(elem.get("byte_offset")),
        byte_size=_to_int(elem.get("byte_size")),
    )


def extract_event_state(xml_path, event_id):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    event_elem = None
    for event in root.findall(".//event"):
        if _to_int(event.get("id")) == int(event_id):
            event_elem = event
            break
    if event_elem is None:
        raise ValueError(f"event {event_id} not found in {xml_path}")

    vertex_buffers = []
    vbs_elem = event_elem.find("vertex_buffers")
    if vbs_elem is not None:
        for vb in vbs_elem.findall("vb"):
            vertex_buffers.append(_parse_buffer(vb))

    ib_elem = event_elem.find("index_buffer")
    index_buffer = _parse_buffer(ib_elem) if ib_elem is not None else None

    return EventState(
        index_buffer=index_buffer,
        vertex_buffers=vertex_buffers,
        textures=[],
        shaders=[],
    )
