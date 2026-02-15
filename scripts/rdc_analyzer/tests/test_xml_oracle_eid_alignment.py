import importlib

from rdc_analyzer.parse_rdc_xml import parse_rdc_xml
from rdc_analyzer.rdc_parser import ChunkInfo, VulkanChunk

_analyze_rdc = importlib.import_module("rdc_analyzer.analyze_rdc")


def _mk_chunk(chunk_id: int) -> ChunkInfo:
    return ChunkInfo(chunk_id=chunk_id, flags=0, length=0, data_offset=0)


def _mk_xml(chunks: list[tuple[int, str]]) -> str:
    # Minimal XML sufficient for parse_rdc_xml.py.
    # NOTE: chunkIndex is not consumed by parse_rdc_xml today; ordering is.
    lines = [
        "<?xml version=\"1.0\"?>",
        "<rdc>",
        "  <header>",
        "    <driver id=\"3\">Vulkan</driver>",
        "    <machineIdent>0</machineIdent>",
        "    <thumbnail width=\"1\" height=\"1\">thumb.png</thumbnail>",
        "  </header>",
        "  <chunks version=\"19\">",
    ]

    for idx, (chunk_id, chunk_name) in enumerate(chunks):
        lines.append(
            "    <chunk id=\"%d\" chunkIndex=\"%d\" name=\"%s\" length=\"0\" threadID=\"1\" "
            "timestamp=\"0\" duration=\"0\">" % (chunk_id, idx, chunk_name)
        )
        lines.append("      <callstack />")
        lines.append("    </chunk>")

    lines.extend(
        [
            "  </chunks>",
            "</rdc>",
            "",
        ]
    )

    return "\n".join(lines)


def test_xml_oracle_eventid_matches_chunk_index_to_eid_mapping(tmp_path):
    # A mixed stream: bindings (skip) + legacy/modern markers + auxiliary + draw variants.
    chunk_stream: list[tuple[int, str]] = [
        (int(VulkanChunk.vkCmdBindPipeline), "vkCmdBindPipeline"),
        (int(VulkanChunk.vkCmdDebugMarkerBeginEXT), "vkCmdDebugMarkerBeginEXT"),
        (int(VulkanChunk.vkCmdBeginDebugUtilsLabelEXT), "vkCmdBeginDebugUtilsLabelEXT"),
        (int(VulkanChunk.vkCmdClearAttachments), "vkCmdClearAttachments"),
        (int(VulkanChunk.vkCmdDrawMeshTasksEXT), "vkCmdDrawMeshTasksEXT"),
        (int(VulkanChunk.vkCmdBindDescriptorSets), "vkCmdBindDescriptorSets"),
        (int(VulkanChunk.vkCmdCopyImageToBuffer2), "vkCmdCopyImageToBuffer2"),
        (int(VulkanChunk.vkCmdDebugMarkerInsertEXT), "vkCmdDebugMarkerInsertEXT"),
        (int(VulkanChunk.vkCmdResolveImage2), "vkCmdResolveImage2"),
        (int(VulkanChunk.vkCmdDrawIndirectCount), "vkCmdDrawIndirectCount"),
        (int(VulkanChunk.vkCmdInsertDebugUtilsLabelEXT), "vkCmdInsertDebugUtilsLabelEXT"),
        (int(VulkanChunk.vkCmdDebugMarkerEndEXT), "vkCmdDebugMarkerEndEXT"),
        (int(VulkanChunk.vkCmdEndDebugUtilsLabelEXT), "vkCmdEndDebugUtilsLabelEXT"),
        (int(VulkanChunk.vkCmdDrawIndexedIndirectCount), "vkCmdDrawIndexedIndirectCount"),
    ]

    xml_path = tmp_path / "synthetic_vulkan_capture.xml"
    xml_path.write_text(_mk_xml(chunk_stream), encoding="utf-8")

    xml_data = parse_rdc_xml(str(xml_path))
    xml_events = xml_data.get("events", [])

    chunks = [_mk_chunk(chunk_id) for (chunk_id, _name) in chunk_stream]
    mapping = _analyze_rdc.build_vulkan_chunk_index_to_eid(chunks)

    event_chunk_indices = sorted(mapping.keys())

    assert len(event_chunk_indices) == len(xml_events)

    expected_event_names = [chunk_stream[idx][1] for idx in event_chunk_indices]
    actual_event_names = [event["name"] for event in xml_events]
    assert actual_event_names == expected_event_names

    for i, chunk_index in enumerate(event_chunk_indices):
        assert xml_events[i]["eventId"] == mapping[chunk_index]
