"""
Vulkan/RDC 枚举定义
===================

包含 Vulkan API Chunk 类型和相关枚举。

从 rdc_parser.py 提取，用于模块化解析。
"""

from enum import IntEnum, IntFlag
from .constants import FIRST_DRIVER_CHUNK


# ============================================================================
# Vulkan Chunk 类型
# ============================================================================

class VulkanChunk(IntEnum):
    """Vulkan API Chunk 类型
    
    基于 RenderDoc 源码 renderdoc/driver/vulkan/vk_common.h VulkanChunk 枚举
    FirstDriverChunk = 1000
    """
    # 设备/资源创建 (1000-1023)
    vkEnumeratePhysicalDevices = FIRST_DRIVER_CHUNK + 0
    vkCreateDevice = FIRST_DRIVER_CHUNK + 1
    vkGetDeviceQueue = FIRST_DRIVER_CHUNK + 2
    vkAllocateMemory = FIRST_DRIVER_CHUNK + 3
    vkUnmapMemory = FIRST_DRIVER_CHUNK + 4
    vkFlushMappedMemoryRanges = FIRST_DRIVER_CHUNK + 5
    vkCreateCommandPool = FIRST_DRIVER_CHUNK + 6
    vkResetCommandPool = FIRST_DRIVER_CHUNK + 7
    vkAllocateCommandBuffers = FIRST_DRIVER_CHUNK + 8
    vkCreateFramebuffer = FIRST_DRIVER_CHUNK + 9
    vkCreateRenderPass = FIRST_DRIVER_CHUNK + 10
    vkCreateDescriptorPool = FIRST_DRIVER_CHUNK + 11
    vkCreateDescriptorSetLayout = FIRST_DRIVER_CHUNK + 12
    vkCreateBuffer = FIRST_DRIVER_CHUNK + 13
    vkCreateBufferView = FIRST_DRIVER_CHUNK + 14
    vkCreateImage = FIRST_DRIVER_CHUNK + 15
    vkCreateImageView = FIRST_DRIVER_CHUNK + 16
    vkCreateDepthTargetView = FIRST_DRIVER_CHUNK + 17
    vkCreateSampler = FIRST_DRIVER_CHUNK + 18
    vkCreateShaderModule = FIRST_DRIVER_CHUNK + 19  # = 1019
    vkCreatePipelineLayout = FIRST_DRIVER_CHUNK + 20
    vkCreatePipelineCache = FIRST_DRIVER_CHUNK + 21
    vkCreateGraphicsPipelines = FIRST_DRIVER_CHUNK + 22  # = 1022
    vkCreateComputePipelines = FIRST_DRIVER_CHUNK + 23   # = 1023
    
    # Command Buffer 操作 (1024-1088)
    vkGetSwapchainImagesKHR = FIRST_DRIVER_CHUNK + 24
    vkCreateSemaphore = FIRST_DRIVER_CHUNK + 25
    vkCreateFence = FIRST_DRIVER_CHUNK + 26
    vkGetFenceStatus = FIRST_DRIVER_CHUNK + 27
    vkResetFences = FIRST_DRIVER_CHUNK + 28
    vkWaitForFences = FIRST_DRIVER_CHUNK + 29
    vkCreateEvent = FIRST_DRIVER_CHUNK + 30
    vkGetEventStatus = FIRST_DRIVER_CHUNK + 31
    vkSetEvent = FIRST_DRIVER_CHUNK + 32
    vkResetEvent = FIRST_DRIVER_CHUNK + 33
    vkCreateQueryPool = FIRST_DRIVER_CHUNK + 34
    vkAllocateDescriptorSets = FIRST_DRIVER_CHUNK + 35
    vkUpdateDescriptorSets = FIRST_DRIVER_CHUNK + 36
    vkBeginCommandBuffer = FIRST_DRIVER_CHUNK + 37
    vkEndCommandBuffer = FIRST_DRIVER_CHUNK + 38
    vkQueueWaitIdle = FIRST_DRIVER_CHUNK + 39
    vkDeviceWaitIdle = FIRST_DRIVER_CHUNK + 40
    vkQueueSubmit = FIRST_DRIVER_CHUNK + 41
    vkBindBufferMemory = FIRST_DRIVER_CHUNK + 42
    vkBindImageMemory = FIRST_DRIVER_CHUNK + 43
    vkQueueBindSparse = FIRST_DRIVER_CHUNK + 44
    vkCmdBeginRenderPass = FIRST_DRIVER_CHUNK + 45
    vkCmdNextSubpass = FIRST_DRIVER_CHUNK + 46
    vkCmdExecuteCommands = FIRST_DRIVER_CHUNK + 47
    vkCmdEndRenderPass = FIRST_DRIVER_CHUNK + 48
    vkCmdBindPipeline = FIRST_DRIVER_CHUNK + 49  # = 1049 ★ 关键
    vkCmdSetViewport = FIRST_DRIVER_CHUNK + 50
    vkCmdSetScissor = FIRST_DRIVER_CHUNK + 51
    vkCmdSetLineWidth = FIRST_DRIVER_CHUNK + 52
    vkCmdSetDepthBias = FIRST_DRIVER_CHUNK + 53
    vkCmdSetBlendConstants = FIRST_DRIVER_CHUNK + 54
    vkCmdSetDepthBounds = FIRST_DRIVER_CHUNK + 55
    vkCmdSetStencilCompareMask = FIRST_DRIVER_CHUNK + 56
    vkCmdSetStencilWriteMask = FIRST_DRIVER_CHUNK + 57
    vkCmdSetStencilReference = FIRST_DRIVER_CHUNK + 58
    vkCmdBindDescriptorSets = FIRST_DRIVER_CHUNK + 59
    vkCmdBindVertexBuffers = FIRST_DRIVER_CHUNK + 60
    vkCmdBindIndexBuffer = FIRST_DRIVER_CHUNK + 61
    vkCmdCopyBufferToImage = FIRST_DRIVER_CHUNK + 62
    vkCmdCopyImageToBuffer = FIRST_DRIVER_CHUNK + 63
    vkCmdCopyBuffer = FIRST_DRIVER_CHUNK + 64
    vkCmdCopyImage = FIRST_DRIVER_CHUNK + 65
    vkCmdBlitImage = FIRST_DRIVER_CHUNK + 66
    vkCmdResolveImage = FIRST_DRIVER_CHUNK + 67
    vkCmdUpdateBuffer = FIRST_DRIVER_CHUNK + 68
    vkCmdFillBuffer = FIRST_DRIVER_CHUNK + 69
    vkCmdPushConstants = FIRST_DRIVER_CHUNK + 70
    vkCmdClearColorImage = FIRST_DRIVER_CHUNK + 71
    vkCmdClearDepthStencilImage = FIRST_DRIVER_CHUNK + 72
    vkCmdClearAttachments = FIRST_DRIVER_CHUNK + 73
    vkCmdPipelineBarrier = FIRST_DRIVER_CHUNK + 74
    vkCmdWriteTimestamp = FIRST_DRIVER_CHUNK + 75
    vkCmdCopyQueryPoolResults = FIRST_DRIVER_CHUNK + 76
    vkCmdBeginQuery = FIRST_DRIVER_CHUNK + 77
    vkCmdEndQuery = FIRST_DRIVER_CHUNK + 78
    vkCmdResetQueryPool = FIRST_DRIVER_CHUNK + 79
    vkCmdSetEvent = FIRST_DRIVER_CHUNK + 80
    vkCmdResetEvent = FIRST_DRIVER_CHUNK + 81
    vkCmdWaitEvents = FIRST_DRIVER_CHUNK + 82
    vkCmdDraw = FIRST_DRIVER_CHUNK + 83  # = 1083 ★ Draw 调用
    vkCmdDrawIndirect = FIRST_DRIVER_CHUNK + 84
    vkCmdDrawIndexed = FIRST_DRIVER_CHUNK + 85  # = 1085 ★ DrawIndexed 调用
    vkCmdDrawIndexedIndirect = FIRST_DRIVER_CHUNK + 86
    vkCmdDispatch = FIRST_DRIVER_CHUNK + 87  # = 1087 ★ Compute Dispatch
    vkCmdDispatchIndirect = FIRST_DRIVER_CHUNK + 88
    
    # Debug Markers (旧版 VK_EXT_debug_marker)
    vkCmdDebugMarkerBeginEXT = FIRST_DRIVER_CHUNK + 89
    vkCmdDebugMarkerInsertEXT = FIRST_DRIVER_CHUNK + 90
    vkCmdDebugMarkerEndEXT = FIRST_DRIVER_CHUNK + 91
    vkDebugMarkerSetObjectNameEXT = FIRST_DRIVER_CHUNK + 92
    
    # 更多扩展 (1093-1108)
    vkCreateSwapchainKHR = FIRST_DRIVER_CHUNK + 93
    SetShaderDebugPath = FIRST_DRIVER_CHUNK + 94
    vkRegisterDeviceEventEXT = FIRST_DRIVER_CHUNK + 95
    vkRegisterDisplayEventEXT = FIRST_DRIVER_CHUNK + 96
    vkCmdIndirectSubCommand = FIRST_DRIVER_CHUNK + 97
    vkCmdPushDescriptorSet = FIRST_DRIVER_CHUNK + 98
    vkCmdPushDescriptorSetWithTemplate = FIRST_DRIVER_CHUNK + 99
    vkCreateDescriptorUpdateTemplate = FIRST_DRIVER_CHUNK + 100
    vkUpdateDescriptorSetWithTemplate = FIRST_DRIVER_CHUNK + 101
    vkBindBufferMemory2 = FIRST_DRIVER_CHUNK + 102
    vkBindImageMemory2 = FIRST_DRIVER_CHUNK + 103
    vkCmdWriteBufferMarkerAMD = FIRST_DRIVER_CHUNK + 104
    vkSetDebugUtilsObjectNameEXT = FIRST_DRIVER_CHUNK + 105  # = 1105 资源命名
    
    # VK_EXT_debug_utils (新版 Debug Markers)
    vkQueueBeginDebugUtilsLabelEXT = FIRST_DRIVER_CHUNK + 106
    vkQueueEndDebugUtilsLabelEXT = FIRST_DRIVER_CHUNK + 107
    vkQueueInsertDebugUtilsLabelEXT = FIRST_DRIVER_CHUNK + 108
    vkCmdBeginDebugUtilsLabelEXT = FIRST_DRIVER_CHUNK + 109  # = 1109 ★ Push Marker
    vkCmdEndDebugUtilsLabelEXT = FIRST_DRIVER_CHUNK + 110    # = 1110 ★ Pop Marker
    vkCmdInsertDebugUtilsLabelEXT = FIRST_DRIVER_CHUNK + 111 # = 1111 单点 Marker


    # Draw variants (values verified against renderdoc/driver/vulkan/vk_common.h)
    vkCmdDrawIndirectCount = FIRST_DRIVER_CHUNK + 116  # = 1116
    vkCmdDrawIndexedIndirectCount = FIRST_DRIVER_CHUNK + 117  # = 1117

    # Mesh shader draws (VK_EXT_mesh_shader)
    vkCmdDrawMeshTasksEXT = FIRST_DRIVER_CHUNK + 198  # = 1198
    vkCmdDrawMeshTasksIndirectEXT = FIRST_DRIVER_CHUNK + 199  # = 1199
    vkCmdDrawMeshTasksIndirectCountEXT = FIRST_DRIVER_CHUNK + 200  # = 1200


# ============================================================================
# Chunk ID 集合 (用于快速判断)
# ============================================================================

VULKAN_DRAW_CHUNK_IDS = {
    VulkanChunk.vkCmdDraw,
    VulkanChunk.vkCmdDrawIndirect,
    VulkanChunk.vkCmdDrawIndexed,
    VulkanChunk.vkCmdDrawIndexedIndirect,
    VulkanChunk.vkCmdDrawIndirectCount,
    VulkanChunk.vkCmdDrawIndexedIndirectCount,
    VulkanChunk.vkCmdDrawMeshTasksEXT,
    VulkanChunk.vkCmdDrawMeshTasksIndirectEXT,
    VulkanChunk.vkCmdDrawMeshTasksIndirectCountEXT,
}

VULKAN_DISPATCH_CHUNK_IDS = {
    VulkanChunk.vkCmdDispatch,
    VulkanChunk.vkCmdDispatchIndirect,
}

VULKAN_MARKER_BEGIN_CHUNK_IDS = {
    VulkanChunk.vkCmdDebugMarkerBeginEXT,
    VulkanChunk.vkCmdBeginDebugUtilsLabelEXT,
}

VULKAN_MARKER_END_CHUNK_IDS = {
    VulkanChunk.vkCmdDebugMarkerEndEXT,
    VulkanChunk.vkCmdEndDebugUtilsLabelEXT,
}


# ============================================================================
# VkFormat 名称映射
# ============================================================================

VK_FORMAT_NAMES = {
    0: "VK_FORMAT_UNDEFINED",
    1: "R4G4_UNORM_PACK8",
    2: "R4G4B4A4_UNORM_PACK16",
    3: "B4G4R4A4_UNORM_PACK16",
    4: "R5G6B5_UNORM_PACK16",
    5: "B5G6R5_UNORM_PACK16",
    9: "R8_UNORM",
    10: "R8_SNORM",
    13: "R8_UINT",
    14: "R8_SINT",
    15: "R8_SRGB",
    16: "R8G8_UNORM",
    20: "R8G8_UINT",
    37: "R8G8B8A8_UNORM",
    38: "R8G8B8A8_SNORM",
    41: "R8G8B8A8_UINT",
    42: "R8G8B8A8_SINT",
    43: "R8G8B8A8_SRGB",
    44: "B8G8R8A8_UNORM",
    50: "B8G8R8A8_SRGB",
    51: "A8B8G8R8_UNORM_PACK32",
    57: "A8B8G8R8_SRGB_PACK32",
    64: "A2B10G10R10_UNORM_PACK32",
    70: "R16_UNORM",
    74: "R16_UINT",
    76: "R16_SFLOAT",
    77: "R16G16_UNORM",
    83: "R16G16_SFLOAT",
    91: "R16G16B16A16_UNORM",
    95: "R16G16B16A16_UINT",
    97: "R16G16B16A16_SFLOAT",
    98: "R32_UINT",
    99: "R32_SINT",
    100: "R32_SFLOAT",
    103: "R32G32_SFLOAT",
    106: "R32G32B32_SFLOAT",
    109: "R32G32B32A32_SFLOAT",
    122: "B10G11R11_UFLOAT_PACK32",
    123: "E5B9G9R9_UFLOAT_PACK32",
    124: "D16_UNORM",
    125: "X8_D24_UNORM_PACK32",
    126: "D32_SFLOAT",
    127: "S8_UINT",
    128: "D16_UNORM_S8_UINT",
    129: "D24_UNORM_S8_UINT",
    130: "D32_SFLOAT_S8_UINT",
    # 压缩格式
    131: "BC1_RGB_UNORM_BLOCK",
    132: "BC1_RGB_SRGB_BLOCK",
    133: "BC1_RGBA_UNORM_BLOCK",
    135: "BC2_UNORM_BLOCK",
    137: "BC3_UNORM_BLOCK",
    139: "BC4_UNORM_BLOCK",
    141: "BC5_UNORM_BLOCK",
    143: "BC6H_UFLOAT_BLOCK",
    144: "BC6H_SFLOAT_BLOCK",
    145: "BC7_UNORM_BLOCK",
    146: "BC7_SRGB_BLOCK",
    # ETC2 (移动端常用)
    147: "ETC2_R8G8B8_UNORM_BLOCK",
    148: "ETC2_R8G8B8_SRGB_BLOCK",
    149: "ETC2_R8G8B8A1_UNORM_BLOCK",
    151: "ETC2_R8G8B8A8_UNORM_BLOCK",
    152: "ETC2_R8G8B8A8_SRGB_BLOCK",
    153: "EAC_R11_UNORM_BLOCK",
    155: "EAC_R11G11_UNORM_BLOCK",
    # ASTC (移动端常用)
    157: "ASTC_4x4_UNORM_BLOCK",
    158: "ASTC_4x4_SRGB_BLOCK",
    159: "ASTC_5x4_UNORM_BLOCK",
    161: "ASTC_5x5_UNORM_BLOCK",
    163: "ASTC_6x5_UNORM_BLOCK",
    165: "ASTC_6x6_UNORM_BLOCK",
    167: "ASTC_8x5_UNORM_BLOCK",
    169: "ASTC_8x6_UNORM_BLOCK",
    171: "ASTC_8x8_UNORM_BLOCK",
    173: "ASTC_10x5_UNORM_BLOCK",
    175: "ASTC_10x6_UNORM_BLOCK",
    177: "ASTC_10x8_UNORM_BLOCK",
    179: "ASTC_10x10_UNORM_BLOCK",
    181: "ASTC_12x10_UNORM_BLOCK",
    183: "ASTC_12x12_UNORM_BLOCK",
}


# ============================================================================
# Vulkan 枚举类
# ============================================================================

class VkImageType(IntEnum):
    """VkImageType 枚举"""
    TYPE_1D = 0
    TYPE_2D = 1
    TYPE_3D = 2


class VkImageUsage(IntFlag):
    """VkImageUsageFlags"""
    TRANSFER_SRC = 0x00000001
    TRANSFER_DST = 0x00000002
    SAMPLED = 0x00000004
    STORAGE = 0x00000008
    COLOR_ATTACHMENT = 0x00000010
    DEPTH_STENCIL_ATTACHMENT = 0x00000020
    TRANSIENT_ATTACHMENT = 0x00000040
    INPUT_ATTACHMENT = 0x00000080


class VkSampleCount(IntEnum):
    """VkSampleCountFlagBits"""
    COUNT_1 = 0x00000001
    COUNT_2 = 0x00000002
    COUNT_4 = 0x00000004
    COUNT_8 = 0x00000008
    COUNT_16 = 0x00000010
    COUNT_32 = 0x00000020
    COUNT_64 = 0x00000040


# ============================================================================
# RDC 通用枚举
# ============================================================================

class RDCDriver(IntEnum):
    """RDC 驱动类型 (来自 renderdoc/core/core.h)"""
    Unknown = 0
    D3D11 = 1
    OpenGL = 2
    Mantle = 3
    D3D12 = 4
    D3D10 = 5
    D3D9 = 6
    Image = 7
    Vulkan = 8
    OpenGLES = 9
    D3D8 = 10
    Metal = 11


class SectionType(IntEnum):
    """RDC Section 类型"""
    Unknown = 0
    FrameCapture = 1
    ResolveDatabase = 2
    Bookmarks = 3
    Notes = 4
    ResourceRenames = 5
    AMDRGPProfile = 6
    ExtendedThumbnail = 7
    EmbeddedLogfile = 8
    EditedShaders = 9
    D3D12Core = 10
    D3D12SDKLayers = 11
    EmbeddedExternalFiles = 12


class SectionFlags(IntFlag):
    """RDC Section 标志"""
    NoFlags = 0x00
    LZ4Compressed = 0x02
    ZstdCompressed = 0x04
    ASCIIStored = 0x10
