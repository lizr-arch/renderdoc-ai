import importlib

from rdc_analyzer.parsers.draw_event_parser import DrawEventParser
from rdc_analyzer.rdc_parser import ChunkInfo, VulkanChunk

_analyze_rdc = importlib.import_module("rdc_analyzer.analyze_rdc")


def _mk_chunk(chunk_id: int) -> ChunkInfo:
    return ChunkInfo(chunk_id=chunk_id, flags=0, length=0, data_offset=0)


def test_vulkanchunk_draw_variant_values_are_stable():
    assert int(VulkanChunk.vkCmdDrawIndirectCount) == 1116
    assert int(VulkanChunk.vkCmdDrawIndexedIndirectCount) == 1117
    assert int(VulkanChunk.vkCmdDrawMeshTasksEXT) == 1198
    assert int(VulkanChunk.vkCmdDrawMeshTasksIndirectEXT) == 1199
    assert int(VulkanChunk.vkCmdDrawMeshTasksIndirectCountEXT) == 1200


def test_vulkanchunk_copy_blit_resolve2_values_are_stable():
    assert int(VulkanChunk.vkCmdCopyBuffer2) == 1153
    assert int(VulkanChunk.vkCmdCopyImage2) == 1154
    assert int(VulkanChunk.vkCmdCopyBufferToImage2) == 1155
    assert int(VulkanChunk.vkCmdCopyImageToBuffer2) == 1156
    assert int(VulkanChunk.vkCmdBlitImage2) == 1157
    assert int(VulkanChunk.vkCmdResolveImage2) == 1158


def test_build_vulkan_chunk_index_to_eid_counts_aux_variants2():
    chunks = [
        _mk_chunk(int(VulkanChunk.vkCmdBindPipeline)),  # binding: should NOT consume eid
        _mk_chunk(int(VulkanChunk.vkCmdCopyImageToBuffer2)),
        _mk_chunk(int(VulkanChunk.vkCmdResolveImage2)),
    ]

    mapping = _analyze_rdc.build_vulkan_chunk_index_to_eid(chunks)

    assert mapping == {
        1: 0,
        2: 1,
    }


def test_draw_event_parser_emits_draw_variants():
    chunks = [
        _mk_chunk(int(VulkanChunk.vkCmdDrawIndirectCount)),
        _mk_chunk(int(VulkanChunk.vkCmdDrawMeshTasksEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdDrawMeshTasksIndirectCountEXT)),
    ]

    parser = DrawEventParser(frame_data=b"", chunks=chunks)
    events, pipelines = parser.extract_all()

    assert pipelines == {}
    assert [e.event_type for e in events] == [
        "draw_indirect_count",
        "draw_mesh_tasks",
        "draw_mesh_tasks_indirect_count",
    ]

    assert [e.event_name for e in events] == [
        "DrawIndirectCount",
        "DrawMeshTasks",
        "DrawMeshTasksIndirectCount",
    ]


def test_build_vulkan_chunk_index_to_eid_counts_draw_variants():
    chunks = [
        _mk_chunk(int(VulkanChunk.vkCmdBindPipeline)),  # binding: should NOT consume eid
        _mk_chunk(int(VulkanChunk.vkCmdDrawIndirectCount)),
        _mk_chunk(int(VulkanChunk.vkCmdDrawMeshTasksEXT)),
    ]

    mapping = _analyze_rdc.build_vulkan_chunk_index_to_eid(chunks)

    assert mapping == {
        1: 0,
        2: 1,
    }
