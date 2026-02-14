import importlib

from rdc_analyzer.rdc_parser import ChunkInfo, VulkanChunk

_analyze_rdc = importlib.import_module("rdc_analyzer.analyze_rdc")


def _mk_chunk(chunk_id: int) -> ChunkInfo:
    return ChunkInfo(chunk_id=chunk_id, flags=0, length=0, data_offset=0)


def test_build_vulkan_chunk_index_to_eid_skips_bindings_counts_events():
    chunks = [
        _mk_chunk(int(VulkanChunk.vkCmdBindPipeline)),
        _mk_chunk(int(VulkanChunk.vkCmdBeginDebugUtilsLabelEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdCopyBufferToImage)),
        _mk_chunk(int(VulkanChunk.vkCmdDrawIndexed)),
        _mk_chunk(int(VulkanChunk.vkCmdBindDescriptorSets)),
        _mk_chunk(int(VulkanChunk.vkCmdInsertDebugUtilsLabelEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdDispatch)),
        _mk_chunk(int(VulkanChunk.vkCmdEndDebugUtilsLabelEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdClearColorImage)),
        _mk_chunk(int(VulkanChunk.vkCmdDraw)),
    ]

    mapping = _analyze_rdc.build_vulkan_chunk_index_to_eid(chunks)

    assert mapping == {
        1: 0,
        2: 1,
        3: 2,
        5: 3,
        6: 4,
        7: 5,
        8: 6,
        9: 7,
    }

    assert 0 not in mapping
    assert 4 not in mapping
