from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass
class DrawEvent:
    event_id: int
    chunk_index: int
    name: str
    api: str


@dataclass
class VulkanDrawIndexedCall:
    event_id: int
    index_count: int
    instance_count: int
    first_index: int
    vertex_offset: int
    first_instance: int


def _to_int(value, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _detect_api_from_xml(xml_path: str) -> str:
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "driver":
            if elem.text and elem.text.strip():
                return elem.text.strip()
            return "Unknown"
        elem.clear()
    return "Unknown"


def iter_draw_events(xml_path: str):
    api = _detect_api_from_xml(xml_path)

    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != "chunk":
            continue

        name = elem.get("name", "")
        if "Draw" not in name and "Dispatch" not in name:
            elem.clear()
            continue

        chunk_index = _to_int(elem.get("chunkIndex"), default=0)
        yield DrawEvent(
            event_id=chunk_index,
            chunk_index=chunk_index,
            name=name,
            api=api,
        )
        elem.clear()


def _parse_index_format(index_type: str) -> str:
    if "UINT32" in index_type:
        return "uint32"
    return "uint16"


def _parse_bind_index_buffer(chunk: ET.Element) -> dict:
    buffer_elem = chunk.find("./ResourceId[@name='buffer']")
    offset_elem = chunk.find("./uint[@name='offset']")
    index_type_elem = chunk.find("./enum[@name='indexType']")

    index_type = ""
    if index_type_elem is not None:
        index_type = index_type_elem.get("string", "")

    return {
        "resource_id": _to_int(buffer_elem.text if buffer_elem is not None else None),
        "byte_offset": _to_int(offset_elem.text if offset_elem is not None else None),
        "index_format": _parse_index_format(index_type),
    }


def _read_numeric_text(chunk: ET.Element, xpath: str, default: int = 0) -> int:
    elem = chunk.find(xpath)
    if elem is None:
        return default
    return _to_int(elem.text, default=default)


def _parse_bind_vertex_buffers(chunk: ET.Element) -> list[dict]:
    buffers_array = chunk.find("./array[@name='pBuffers']")
    offsets_array = chunk.find("./array[@name='pOffsets']")

    buffer_ids = []
    if buffers_array is not None:
        for elem in buffers_array.findall("ResourceId"):
            buffer_ids.append(_to_int(elem.text))

    offsets = []
    if offsets_array is not None:
        for elem in offsets_array.findall("uint"):
            offsets.append(_to_int(elem.text))

    bindings = []
    for index, resource_id in enumerate(buffer_ids):
        byte_offset = offsets[index] if index < len(offsets) else 0
        bindings.append({"resource_id": resource_id, "byte_offset": byte_offset})

    return bindings


def _parse_draw_indexed_chunk(chunk: ET.Element, event_id: int) -> VulkanDrawIndexedCall:
    return VulkanDrawIndexedCall(
        event_id=event_id,
        index_count=_read_numeric_text(chunk, "./uint[@name='indexCount']"),
        instance_count=_read_numeric_text(chunk, "./uint[@name='instanceCount']"),
        first_index=_read_numeric_text(chunk, "./uint[@name='firstIndex']"),
        vertex_offset=_read_numeric_text(chunk, "./int[@name='vertexOffset']"),
        first_instance=_read_numeric_text(chunk, "./uint[@name='firstInstance']"),
    )


def extract_vulkan_bindings_for_event(xml_path: str, event_id: int) -> dict:
    event_id = int(event_id)
    index_binding = None
    vertex_bindings = []
    draw_info = None
    found = False

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        name = chunk.get("name", "")
        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)

        if name == "vkCmdBindIndexBuffer":
            index_binding = _parse_bind_index_buffer(chunk)
        elif name == "vkCmdBindVertexBuffers":
            vertex_bindings = _parse_bind_vertex_buffers(chunk)

        if chunk_index == event_id:
            found = True
            if name == "vkCmdDrawIndexed":
                draw_info = {
                    "index_count": _read_numeric_text(chunk, "./uint[@name='indexCount']"),
                    "instance_count": _read_numeric_text(chunk, "./uint[@name='instanceCount']"),
                    "first_index": _read_numeric_text(chunk, "./uint[@name='firstIndex']"),
                    "vertex_offset": _read_numeric_text(chunk, "./int[@name='vertexOffset']"),
                    "first_instance": _read_numeric_text(chunk, "./uint[@name='firstInstance']"),
                }
            break

        chunk.clear()

    if not found:
        raise ValueError(f"event {event_id} not found")

    return {
        "index_buffer": index_binding,
        "vertex_buffers": vertex_bindings,
        "draw": draw_info,
    }


def extract_vulkan_draw_indexed_call(xml_path: str, event_id: int) -> VulkanDrawIndexedCall:
    event_id = int(event_id)
    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)
        if chunk_index != event_id:
            chunk.clear()
            continue

        if chunk.get("name", "") != "vkCmdDrawIndexed":
            raise ValueError(f"event {event_id} is not vkCmdDrawIndexed")

        result = _parse_draw_indexed_chunk(chunk, event_id)
        chunk.clear()
        return result

    raise ValueError(f"event {event_id} not found")


def build_vulkan_buffer_memory_maps(xml_path: str) -> tuple[dict, dict, dict]:
    buffer_memory = {}
    memory_initial = {}
    buffer_sizes = {}

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        name = chunk.get("name", "")

        if name == "vkCreateBuffer":
            buffer_elem = chunk.find("./ResourceId[@name='Buffer']")
            if buffer_elem is None:
                buffer_elem = chunk.find("./ResourceId[@name='buffer']")

            size_elem = chunk.find("./struct[@name='CreateInfo']/uint[@name='size']")
            if size_elem is None:
                size_elem = chunk.find("./uint[@name='size']")

            if buffer_elem is not None:
                buffer_id = _to_int(buffer_elem.text)
                buffer_sizes[buffer_id] = _to_int(size_elem.text if size_elem is not None else None)

        elif name == "vkBindBufferMemory":
            buffer_elem = chunk.find("./ResourceId[@name='buffer']")
            memory_elem = chunk.find("./ResourceId[@name='memory']")
            offset_elem = chunk.find("./uint[@name='memoryOffset']")
            if buffer_elem is not None and memory_elem is not None:
                buffer_id = _to_int(buffer_elem.text)
                memory_id = _to_int(memory_elem.text)
                memory_offset = _to_int(offset_elem.text if offset_elem is not None else None)
                buffer_memory[buffer_id] = {
                    "memory_id": memory_id,
                    "memory_offset": memory_offset,
                }

        elif name == "Internal::Initial Contents":
            type_elem = chunk.find("./enum[@name='type']")
            type_name = type_elem.get("string", "") if type_elem is not None else ""
            if type_name != "eResDeviceMemory":
                chunk.clear()
                continue

            memory_id_elem = chunk.find("./ResourceId[@name='id']")
            contents_elem = chunk.find("./buffer[@name='Contents']")
            size_elem = chunk.find("./uint[@name='ContentsSize']")

            if memory_id_elem is not None and contents_elem is not None:
                memory_id = _to_int(memory_id_elem.text)
                memory_initial[memory_id] = {
                    "buffer_index": _to_int(contents_elem.text),
                    "contents_size": _to_int(size_elem.text if size_elem is not None else None),
                }

        chunk.clear()

    return buffer_memory, memory_initial, buffer_sizes
