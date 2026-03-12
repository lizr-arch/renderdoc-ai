import importlib

from rdc_analyzer.rdc_parser import ChunkInfo, VulkanChunk

_analyze_rdc = importlib.import_module("rdc_analyzer.analyze_rdc")


def _mk_chunk(chunk_id: int) -> ChunkInfo:
    return ChunkInfo(chunk_id=chunk_id, flags=0, length=0, data_offset=0)


def test_build_vulkan_chunk_index_to_eid_skips_bindings_counts_events():
    chunks = [
        _mk_chunk(int(VulkanChunk.vkCmdBindPipeline)),
        # Legacy markers (VK_EXT_debug_marker) should consume EID.
        _mk_chunk(int(VulkanChunk.vkCmdDebugMarkerBeginEXT)),
        # Modern markers (VK_EXT_debug_utils) should consume EID.
        _mk_chunk(int(VulkanChunk.vkCmdBeginDebugUtilsLabelEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdCopyBufferToImage)),
        _mk_chunk(int(VulkanChunk.vkCmdResolveImage)),
        _mk_chunk(int(VulkanChunk.vkCmdDrawIndexed)),
        _mk_chunk(int(VulkanChunk.vkCmdBindDescriptorSets)),
        _mk_chunk(int(VulkanChunk.vkCmdDebugMarkerInsertEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdInsertDebugUtilsLabelEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdUpdateBuffer)),
        _mk_chunk(int(VulkanChunk.vkCmdDispatch)),
        _mk_chunk(int(VulkanChunk.vkCmdDebugMarkerEndEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdEndDebugUtilsLabelEXT)),
        _mk_chunk(int(VulkanChunk.vkCmdClearColorImage)),
        _mk_chunk(int(VulkanChunk.vkCmdClearAttachments)),
        _mk_chunk(int(VulkanChunk.vkCmdCopyImageToBuffer)),
        _mk_chunk(int(VulkanChunk.vkCmdFillBuffer)),
        _mk_chunk(int(VulkanChunk.vkCmdDraw)),
    ]

    mapping = _analyze_rdc.build_vulkan_chunk_index_to_eid(chunks)

    assert mapping == {
        1: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
        7: 5,
        8: 6,
        9: 7,
        10: 8,
        11: 9,
        12: 10,
        13: 11,
        14: 12,
        15: 13,
        16: 14,
        17: 15,
    }

    assert 0 not in mapping
    assert 6 not in mapping
