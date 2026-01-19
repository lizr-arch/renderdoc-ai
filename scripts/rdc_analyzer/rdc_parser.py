#!/usr/bin/env python3
"""
RDC File Parser - 独立解析 RenderDoc 捕获文件

基于 RenderDoc 源码逆向分析，无需 RenderDoc GUI 即可提取 Shader 数据。

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import struct
import os
import json
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import List, Optional, Tuple, BinaryIO, Dict
from pathlib import Path

# ============================================================================
# 常量定义
# ============================================================================

RDC_MAGIC = 0x434F4452  # 'RDOC' in little-endian (实际存储为 RDOC)
RDC_MAGIC_BYTES = b'RDOC'

# 文件版本
RDC_VERSION_1_0 = 0x00000100
RDC_VERSION_1_1 = 0x00000101
RDC_VERSION_1_2 = 0x00000102

# Chunk 标志
CHUNK_INDEX_MASK = 0x0000FFFF
CHUNK_CALLSTACK = 0x00010000
CHUNK_THREAD_ID = 0x00020000
CHUNK_DURATION = 0x00040000
CHUNK_TIMESTAMP = 0x00080000
CHUNK_64BIT_SIZE = 0x00100000

# 对齐
CHUNK_ALIGNMENT = 64

# SPIR-V Magic
SPIRV_MAGIC = 0x07230203

# SPIR-V OpCodes (重要的)
SPIRV_OP_NAME = 5           # OpName: 给ID命名
SPIRV_OP_ENTRY_POINT = 15   # OpEntryPoint: 入口点定义
SPIRV_OP_SOURCE = 3         # OpSource: 源语言信息

# SPIR-V Execution Model (用于识别 shader 类型)
SPIRV_EXEC_VERTEX = 0
SPIRV_EXEC_TESSELLATION_CONTROL = 1
SPIRV_EXEC_TESSELLATION_EVALUATION = 2
SPIRV_EXEC_GEOMETRY = 3
SPIRV_EXEC_FRAGMENT = 4
SPIRV_EXEC_GLCOMPUTE = 5
SPIRV_EXEC_KERNEL = 6
SPIRV_EXEC_TASK_NV = 5267
SPIRV_EXEC_MESH_NV = 5268
SPIRV_EXEC_RAY_GENERATION_KHR = 5313
SPIRV_EXEC_INTERSECTION_KHR = 5314
SPIRV_EXEC_ANY_HIT_KHR = 5315
SPIRV_EXEC_CLOSEST_HIT_KHR = 5316
SPIRV_EXEC_MISS_KHR = 5317
SPIRV_EXEC_CALLABLE_KHR = 5318

SPIRV_EXEC_MODEL_NAMES = {
    SPIRV_EXEC_VERTEX: "Vertex",
    SPIRV_EXEC_TESSELLATION_CONTROL: "TessControl",
    SPIRV_EXEC_TESSELLATION_EVALUATION: "TessEval",
    SPIRV_EXEC_GEOMETRY: "Geometry",
    SPIRV_EXEC_FRAGMENT: "Fragment",
    SPIRV_EXEC_GLCOMPUTE: "Compute",
    SPIRV_EXEC_KERNEL: "Kernel",
    SPIRV_EXEC_TASK_NV: "TaskNV",
    SPIRV_EXEC_MESH_NV: "MeshNV",
    SPIRV_EXEC_RAY_GENERATION_KHR: "RayGen",
    SPIRV_EXEC_INTERSECTION_KHR: "Intersection",
    SPIRV_EXEC_ANY_HIT_KHR: "AnyHit",
    SPIRV_EXEC_CLOSEST_HIT_KHR: "ClosestHit",
    SPIRV_EXEC_MISS_KHR: "Miss",
    SPIRV_EXEC_CALLABLE_KHR: "Callable",
}

# Vulkan Chunk IDs (FirstDriverChunk = 1000)
FIRST_DRIVER_CHUNK = 1000

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


# 需要追踪的 Draw 相关 Chunk ID 集合
DRAW_CHUNK_IDS = {
    VulkanChunk.vkCmdDraw,
    VulkanChunk.vkCmdDrawIndirect,
    VulkanChunk.vkCmdDrawIndexed,
    VulkanChunk.vkCmdDrawIndexedIndirect,
}

DISPATCH_CHUNK_IDS = {
    VulkanChunk.vkCmdDispatch,
    VulkanChunk.vkCmdDispatchIndirect,
}

MARKER_BEGIN_CHUNK_IDS = {
    VulkanChunk.vkCmdDebugMarkerBeginEXT,
    VulkanChunk.vkCmdBeginDebugUtilsLabelEXT,
}

MARKER_END_CHUNK_IDS = {
    VulkanChunk.vkCmdDebugMarkerEndEXT,
    VulkanChunk.vkCmdEndDebugUtilsLabelEXT,
}


# VkFormat 枚举 (来自 vulkan_core.h)
# 只列出常用格式，完整列表超过 200 个
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


# VkImageType 枚举
class VkImageType(IntEnum):
    TYPE_1D = 0
    TYPE_2D = 1
    TYPE_3D = 2


# VkImageUsageFlags
class VkImageUsage(IntFlag):
    TRANSFER_SRC = 0x00000001
    TRANSFER_DST = 0x00000002
    SAMPLED = 0x00000004
    STORAGE = 0x00000008
    COLOR_ATTACHMENT = 0x00000010
    DEPTH_STENCIL_ATTACHMENT = 0x00000020
    TRANSIENT_ATTACHMENT = 0x00000040
    INPUT_ATTACHMENT = 0x00000080


# VkSampleCount
class VkSampleCount(IntEnum):
    COUNT_1 = 0x00000001
    COUNT_2 = 0x00000002
    COUNT_4 = 0x00000004
    COUNT_8 = 0x00000008
    COUNT_16 = 0x00000010
    COUNT_32 = 0x00000020
    COUNT_64 = 0x00000040


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
    """Section 类型"""
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
    """Section 标志"""
    NoFlags = 0x00
    LZ4Compressed = 0x02
    ZstdCompressed = 0x04
    ASCIIStored = 0x10


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class FileHeader:
    """RDC 文件头"""
    magic: bytes
    version: int
    header_length: int
    prog_version: str
    
    @property
    def is_valid(self) -> bool:
        return self.magic == RDC_MAGIC_BYTES
    
    @property
    def version_string(self) -> str:
        major = (self.version >> 8) & 0xFF
        minor = self.version & 0xFF
        return f"v{major}.{minor}"


@dataclass
class Thumbnail:
    """缩略图数据"""
    width: int
    height: int
    data: bytes
    
    @property
    def has_thumbnail(self) -> bool:
        return self.width > 0 and self.height > 0


@dataclass
class CaptureMetaData:
    """捕获元数据"""
    machine_ident: int
    driver_id: RDCDriver
    driver_name: str


@dataclass
class TimeBase:
    """时间基准"""
    time_base: int
    time_freq: float


@dataclass
class SectionInfo:
    """Section 信息"""
    section_type: SectionType
    name: str
    compressed_size: int
    uncompressed_size: int
    version: int
    flags: SectionFlags
    data_offset: int  # 数据在文件中的偏移
    header_offset: int  # Section header 在文件中的偏移
    
    @property
    def is_compressed(self) -> bool:
        return bool(self.flags & (SectionFlags.LZ4Compressed | SectionFlags.ZstdCompressed))
    
    @property
    def compression_type(self) -> str:
        if self.flags & SectionFlags.LZ4Compressed:
            return "LZ4"
        elif self.flags & SectionFlags.ZstdCompressed:
            return "Zstd"
        return "None"


@dataclass
class ChunkInfo:
    """Chunk 信息"""
    chunk_id: int
    flags: int
    length: int
    data_offset: int  # Chunk 数据在解压后 Section 中的偏移
    
    # 可选元数据
    thread_id: Optional[int] = None
    duration_micro: Optional[int] = None
    timestamp_micro: Optional[int] = None
    callstack: Optional[List[int]] = None
    
    @property
    def has_64bit_size(self) -> bool:
        return bool(self.flags & CHUNK_64BIT_SIZE)
    
    @property
    def chunk_name(self) -> str:
        """获取 Chunk 名称"""
        try:
            return VulkanChunk(self.chunk_id).name
        except ValueError:
            if self.chunk_id < FIRST_DRIVER_CHUNK:
                return f"SystemChunk_{self.chunk_id}"
            return f"UnknownChunk_{self.chunk_id}"


@dataclass
class DrawEventContext:
    """Draw/Dispatch 事件的上下文信息
    
    将 Draw Call 与其使用的 Pipeline (进而 Shader) 关联起来。
    """
    chunk_index: int          # 在 FrameCapture 中的 Chunk 索引
    chunk_id: int             # Chunk 类型 ID
    event_type: str           # 'draw', 'draw_indexed', 'dispatch' 等
    pipeline_resource_id: int # 当前绑定的 Pipeline ResourceId
    marker_stack: List[str]   # 当前的 Debug Marker 栈（层级路径）
    
    @property
    def marker_path(self) -> str:
        """获取 Marker 路径字符串（例如 "ShadowPass/Character"）"""
        return "/".join(self.marker_stack) if self.marker_stack else ""
    
    @property
    def event_name(self) -> str:
        """获取可读的事件名称"""
        event_names = {
            'draw': 'Draw',
            'draw_indexed': 'DrawIndexed',
            'draw_indirect': 'DrawIndirect',
            'draw_indexed_indirect': 'DrawIndexedIndirect',
            'dispatch': 'Dispatch',
            'dispatch_indirect': 'DispatchIndirect',
        }
        return event_names.get(self.event_type, self.event_type)


@dataclass
class PipelineInfo:
    """Graphics/Compute Pipeline 信息
    
    关联 Pipeline ResourceId 与其包含的 Shader Module。
    """
    resource_id: int                # Pipeline 的 ResourceId
    pipeline_type: str              # 'graphics' 或 'compute'
    shader_stages: Dict[str, int]   # stage -> shader_module_resource_id 映射
    # 例如: {'VS': 12345, 'PS': 12346}


@dataclass
class ShaderResource:
    """Shader 使用的资源信息
    
    从 SPIR-V 的 OpName 和类型信息中提取的资源描述。
    资源类型通过名称模式推断：
    - Texture: 名称包含 Texture, Image, Map 等
    - Sampler: 名称包含 Sampler
    - Buffer: 名称包含 Buffer, UBO, SSBO 等
    - Uniform: 名称包含 Uniform, Params, Constants 等
    """
    spirv_id: int           # SPIR-V 中的 ID
    name: str               # OpName 定义的名称
    category: str           # 'Texture', 'Sampler', 'Buffer', 'Uniform', 'Other'
    
    @staticmethod
    def classify_name(name: str) -> str:
        """根据名称模式推断资源类型
        
        分类优先级（从高到低）:
        1. 后缀匹配 - 以 'Sampler' 结尾 → Sampler
        2. 排除模式 - 内部类型名等 → Other
        3. 关键词匹配 - Texture/Buffer/Uniform
        """
        if not name:
            return 'Other'
        
        name_lower = name.lower()
        
        # [优先级 1] 后缀精确匹配 - Sampler 后缀
        # 处理如 "Material_Texture2D_0Sampler", "SceneColorSampler" 等
        if name.endswith('Sampler') or name.endswith('_Sampler'):
            return 'Sampler'
        
        # [优先级 2] 排除的模式 - SPIR-V 内部类型名
        exclude_patterns = ['type.', 'in.var.', 'out.var.', '$globals', 'main_']
        if any(p in name_lower for p in exclude_patterns):
            return 'Other'
        
        # [优先级 3a] Texture/Image 模式
        texture_keywords = ['texture', 'image', 'map', 'atlas', 'cubemap', 'render', 
                           'shadow', 'depth', 'stencil', 'color', 'normal', 'specular',
                           'albedo', 'roughness', 'metallic', 'ao', 'emissive',
                           'scene', 'screen', 'gbuffer', 'hdr', 'ldr', 'lut']
        if any(kw in name_lower for kw in texture_keywords):
            return 'Texture'
        
        # [优先级 3b] Buffer 模式
        buffer_keywords = ['buffer', 'ubo', 'ssbo', 'storage', 'instance', 
                          'vertex', 'index', 'indirect', 'data']
        if any(kw in name_lower for kw in buffer_keywords):
            return 'Buffer'
        
        # [优先级 3c] Uniform/Constant 模式
        uniform_keywords = ['uniform', 'constant', 'param', 'setting', 'config',
                           'view', 'primitive', 'material', 'light', 'fog', 
                           'time', 'frame', 'camera', 'transform']
        if any(kw in name_lower for kw in uniform_keywords):
            return 'Uniform'
        
        return 'Other'


@dataclass
class SPIRVEntryPoint:
    """SPIR-V 入口点信息"""
    execution_model: int
    entry_id: int
    name: str
    
    @property
    def stage_name(self) -> str:
        """获取可读的 shader 阶段名称"""
        return SPIRV_EXEC_MODEL_NAMES.get(self.execution_model, f"Unknown({self.execution_model})")
    
    @property
    def short_stage(self) -> str:
        """获取简短的阶段标识 (VS, PS, CS 等)"""
        stage_map = {
            SPIRV_EXEC_VERTEX: "VS",
            SPIRV_EXEC_TESSELLATION_CONTROL: "TCS",
            SPIRV_EXEC_TESSELLATION_EVALUATION: "TES",
            SPIRV_EXEC_GEOMETRY: "GS",
            SPIRV_EXEC_FRAGMENT: "PS",  # 习惯称为 Pixel Shader
            SPIRV_EXEC_GLCOMPUTE: "CS",
            SPIRV_EXEC_KERNEL: "KN",
            SPIRV_EXEC_TASK_NV: "TS",
            SPIRV_EXEC_MESH_NV: "MS",
            SPIRV_EXEC_RAY_GENERATION_KHR: "RG",
            SPIRV_EXEC_INTERSECTION_KHR: "IS",
            SPIRV_EXEC_ANY_HIT_KHR: "AH",
            SPIRV_EXEC_CLOSEST_HIT_KHR: "CH",
            SPIRV_EXEC_MISS_KHR: "MI",
            SPIRV_EXEC_CALLABLE_KHR: "CA",
        }
        return stage_map.get(self.execution_model, "??")


@dataclass
class ShaderInfo:
    """提取的 Shader 信息"""
    resource_id: int
    spirv_data: bytes
    code_size: int
    chunk_offset: int  # 在 FrameCapture 中的偏移
    
    # 可选：解析后的元数据
    _entry_points: Optional[List[SPIRVEntryPoint]] = field(default=None, repr=False)
    _debug_names: Optional[dict] = field(default=None, repr=False)
    
    @property
    def is_valid_spirv(self) -> bool:
        """检查是否是有效的 SPIR-V"""
        if len(self.spirv_data) < 4:
            return False
        magic = struct.unpack('<I', self.spirv_data[:4])[0]
        return magic == SPIRV_MAGIC
    
    @property
    def spirv_version(self) -> str:
        """获取 SPIR-V 版本"""
        if len(self.spirv_data) < 8:
            return "Unknown"
        version = struct.unpack('<I', self.spirv_data[4:8])[0]
        major = (version >> 16) & 0xFF
        minor = (version >> 8) & 0xFF
        return f"{major}.{minor}"
    
    @property
    def entry_points(self) -> List[SPIRVEntryPoint]:
        """获取所有入口点（惰性解析）"""
        if self._entry_points is None:
            self._parse_spirv_metadata()
        return self._entry_points or []
    
    @property
    def primary_entry_point(self) -> Optional[SPIRVEntryPoint]:
        """获取主入口点（通常只有一个）"""
        eps = self.entry_points
        return eps[0] if eps else None
    
    @property
    def entry_name(self) -> str:
        """获取入口点名称（如 main, vs_main 等）"""
        ep = self.primary_entry_point
        return ep.name if ep else "unknown"
    
    @property
    def stage(self) -> str:
        """获取 shader 阶段简称 (VS, PS, CS 等)"""
        ep = self.primary_entry_point
        return ep.short_stage if ep else "??"
    
    @property
    def display_name(self) -> str:
        """获取用于显示的名称，如 "VS:main" 或 "PS:fragment_main" """
        ep = self.primary_entry_point
        if ep:
            return f"{ep.short_stage}:{ep.name}"
        return f"Shader_{self.resource_id:x}"
    
    @property
    def debug_names(self) -> dict:
        """获取所有调试名称（惰性解析）"""
        if self._debug_names is None:
            self._parse_spirv_metadata()
        return self._debug_names or {}
    
    @property
    def friendly_label(self) -> str:
        """
        从 OpName 变量名中选择最有意义的名称作为友好标签。
        
        优先级（按重要性排序）：
        1. UE 渲染管线关键字（如 ReflectionCapture, EyeAdaptation, Shadow 等）
        2. 资源采样器名称（如 SceneColorSampler, InputTexture 等）
        3. Buffer 名称（如 LightDataBuffer 等）
        4. 排除无意义的名称（如 type.*, $Globals, in.var.*, out.var.* 等）
        """
        names = self.debug_names
        if not names:
            return ""
        
        # 重要关键字（UE 渲染管线组件）
        important_keywords = [
            # 光照与阴影
            'Shadow', 'Light', 'Reflection', 'Refraction', 'GI', 'Ambient',
            # 后处理
            'PostProcess', 'Bloom', 'DOF', 'DepthOfField', 'MotionBlur',
            'EyeAdaptation', 'Exposure', 'ToneMap', 'ColorGrad',
            'FXAA', 'TAA', 'SSAO', 'SSR', 'Fog',
            # 渲染阶段
            'BasePass', 'Deferred', 'Forward', 'Translucent', 'Distortion',
            'Velocity', 'PrePass', 'CustomDepth', 'Decal',
            # 资源类型
            'Texture', 'Sampler', 'Buffer', 'Grid', 'Capture',
            # 特效
            'Particle', 'Atmosphere', 'Sky', 'Cloud', 'Water', 'Terrain',
        ]
        
        # 需要排除的无意义前缀
        exclude_prefixes = [
            'type.', '$', 'in.var.', 'out.var.', 'main_', '_',
        ]
        
        # 需要排除的无意义名称
        exclude_names = {
            'Globals', 'View', 'Primitive', 'DrawRectangleParameters',
        }
        
        best_name = ""
        best_score = -1
        
        for target_id, name in names.items():
            # 跳过无意义名称
            if not name or len(name) < 3:
                continue
            if any(name.startswith(prefix) for prefix in exclude_prefixes):
                continue
            if name in exclude_names:
                continue
            
            # 计算重要性分数
            score = 0
            name_lower = name.lower()
            
            for keyword in important_keywords:
                if keyword.lower() in name_lower:
                    score += 10
            
            # 长度适中的名称优先（太短可能无意义，太长可能是路径）
            if 8 <= len(name) <= 40:
                score += 2
            elif 5 <= len(name) < 8:
                score += 1
            
            # 包含大写字母（驼峰命名）更可能是有意义的名称
            if any(c.isupper() for c in name[1:]):
                score += 1
            
            if score > best_score:
                best_score = score
                best_name = name
        
        return best_name
    
    @property
    def all_resources(self) -> List['ShaderResource']:
        """
        获取该 Shader 使用的所有资源列表。
        
        从 OpName 中提取的资源会按名称模式分类为:
        - Texture: 纹理资源
        - Sampler: 采样器
        - Buffer: 缓冲区 (UBO, SSBO 等)
        - Uniform: 统一变量/常量
        - Other: 其他（类型定义、临时变量等）
        
        注意：只返回有意义的资源名称，排除 type.*, in.var.*, out.var.* 等。
        """
        names = self.debug_names
        if not names:
            return []
        
        resources = []
        for spirv_id, name in names.items():
            if not name or len(name) < 3:
                continue
            
            category = ShaderResource.classify_name(name)
            
            # 只返回有意义的资源（排除 Other）
            if category != 'Other':
                resources.append(ShaderResource(
                    spirv_id=spirv_id,
                    name=name,
                    category=category
                ))
        
        # 按类别和名称排序
        category_order = {'Texture': 0, 'Sampler': 1, 'Buffer': 2, 'Uniform': 3}
        resources.sort(key=lambda r: (category_order.get(r.category, 99), r.name))
        
        return resources
    
    @property
    def resource_summary(self) -> dict:
        """
        获取资源使用摘要统计。
        
        返回各类型资源的数量和名称列表，用于快速了解 Shader 的资源需求。
        """
        resources = self.all_resources
        summary = {
            'total': len(resources),
            'by_category': {},
            'texture_count': 0,
            'sampler_count': 0,
            'buffer_count': 0,
            'uniform_count': 0,
        }
        
        for res in resources:
            cat = res.category
            if cat not in summary['by_category']:
                summary['by_category'][cat] = []
            summary['by_category'][cat].append(res.name)
            
            # 计数
            count_key = f"{cat.lower()}_count"
            if count_key in summary:
                summary[count_key] += 1
        
        return summary
    
    def _parse_spirv_metadata(self):
        """解析 SPIR-V 中的元数据（OpName, OpEntryPoint 等）"""
        self._entry_points = []
        self._debug_names = {}
        
        if not self.is_valid_spirv or len(self.spirv_data) < 20:
            return
        
        data = self.spirv_data
        offset = 20  # 跳过 SPIR-V header (5 words)
        
        while offset < len(data) - 4:
            word = struct.unpack_from('<I', data, offset)[0]
            word_count = word >> 16
            opcode = word & 0xFFFF
            
            if word_count == 0:
                break
            
            inst_size = word_count * 4
            if offset + inst_size > len(data):
                break
            
            # OpEntryPoint: 入口点定义
            # 格式: OpEntryPoint <execution_model> <entry_id> "<name>" [interface_ids...]
            if opcode == SPIRV_OP_ENTRY_POINT and word_count >= 4:
                exec_model = struct.unpack_from('<I', data, offset + 4)[0]
                entry_id = struct.unpack_from('<I', data, offset + 8)[0]
                # 名称从 word 3 开始，以 null 终止
                name_start = offset + 12
                name_bytes = data[name_start:offset + inst_size]
                null_idx = name_bytes.find(b'\x00')
                if null_idx >= 0:
                    name = name_bytes[:null_idx].decode('utf-8', errors='replace')
                else:
                    name = name_bytes.decode('utf-8', errors='replace')
                
                self._entry_points.append(SPIRVEntryPoint(
                    execution_model=exec_model,
                    entry_id=entry_id,
                    name=name
                ))
            
            # OpName: 给 ID 命名（用于调试）
            # 格式: OpName <id> "<name>"
            elif opcode == SPIRV_OP_NAME and word_count >= 3:
                target_id = struct.unpack_from('<I', data, offset + 4)[0]
                name_start = offset + 8
                name_bytes = data[name_start:offset + inst_size]
                null_idx = name_bytes.find(b'\x00')
                if null_idx >= 0:
                    name = name_bytes[:null_idx].decode('utf-8', errors='replace')
                else:
                    name = name_bytes.decode('utf-8', errors='replace')
                
                self._debug_names[target_id] = name
            
            offset += inst_size


@dataclass
class TextureInfo:
    """提取的纹理（Image）信息
    
    基于 VkImageCreateInfo 结构:
    - imageType: 1D/2D/3D
    - format: VkFormat
    - extent: (width, height, depth)
    - mipLevels: mipmap 层数
    - arrayLayers: 数组层数
    - samples: MSAA 采样数
    - usage: 用途标志
    """
    resource_id: int
    image_type: int          # VkImageType
    format: int              # VkFormat
    width: int
    height: int
    depth: int
    mip_levels: int
    array_layers: int
    samples: int             # VkSampleCount
    usage: int               # VkImageUsageFlags
    chunk_offset: int        # 在 FrameCapture 中的偏移
    
    @property
    def format_name(self) -> str:
        """获取格式名称"""
        return VK_FORMAT_NAMES.get(self.format, f"VK_FORMAT_{self.format}")
    
    @property
    def type_name(self) -> str:
        """获取图像类型名称"""
        try:
            return VkImageType(self.image_type).name.replace("TYPE_", "")
        except ValueError:
            return f"Unknown({self.image_type})"
    
    @property
    def dimensions(self) -> str:
        """获取尺寸描述"""
        if self.image_type == VkImageType.TYPE_1D:
            return f"{self.width}"
        elif self.image_type == VkImageType.TYPE_3D:
            return f"{self.width}x{self.height}x{self.depth}"
        else:  # 2D
            if self.array_layers > 1:
                return f"{self.width}x{self.height}[{self.array_layers}]"
            return f"{self.width}x{self.height}"
    
    @property
    def msaa_desc(self) -> str:
        """获取 MSAA 描述"""
        if self.samples <= 1:
            return ""
        return f"{self.samples}xMSAA"
    
    @property
    def usage_flags(self) -> List[str]:
        """获取用途标志列表"""
        flags = []
        if self.usage & VkImageUsage.TRANSFER_SRC:
            flags.append("TRANSFER_SRC")
        if self.usage & VkImageUsage.TRANSFER_DST:
            flags.append("TRANSFER_DST")
        if self.usage & VkImageUsage.SAMPLED:
            flags.append("SAMPLED")
        if self.usage & VkImageUsage.STORAGE:
            flags.append("STORAGE")
        if self.usage & VkImageUsage.COLOR_ATTACHMENT:
            flags.append("COLOR_ATTACHMENT")
        if self.usage & VkImageUsage.DEPTH_STENCIL_ATTACHMENT:
            flags.append("DEPTH_STENCIL")
        if self.usage & VkImageUsage.INPUT_ATTACHMENT:
            flags.append("INPUT_ATTACHMENT")
        return flags
    
    @property
    def is_render_target(self) -> bool:
        """是否是渲染目标"""
        return bool(self.usage & (VkImageUsage.COLOR_ATTACHMENT | VkImageUsage.DEPTH_STENCIL_ATTACHMENT))
    
    @property
    def is_depth_stencil(self) -> bool:
        """是否是深度/模板格式"""
        return self.format in (124, 125, 126, 127, 128, 129, 130)  # D16, D24, D32, S8, D16S8, D24S8, D32S8
    
    @property
    def estimated_size_mb(self) -> float:
        """估算纹理大小（MB）"""
        # 简化计算：假设未压缩格式
        bpp = self._get_bytes_per_pixel()
        pixels = self.width * self.height * self.depth
        
        # 考虑 mipmap
        mip_factor = 1.0
        if self.mip_levels > 1:
            mip_factor = 1.333  # 完整 mipchain 约增加 1/3
        
        # 考虑数组层和 MSAA
        total_bytes = pixels * bpp * self.array_layers * self.samples * mip_factor
        return total_bytes / (1024 * 1024)
    
    def _get_bytes_per_pixel(self) -> int:
        """获取每像素字节数（简化估算）"""
        fmt = self.format
        # 压缩格式
        if 131 <= fmt <= 146:  # BC1-BC7
            return 1  # 简化
        if 147 <= fmt <= 156:  # ETC2/EAC
            return 1
        if 157 <= fmt <= 184:  # ASTC
            return 1
        
        # 常见格式
        if fmt in (9, 10, 13, 14, 15, 127):  # R8, S8
            return 1
        if fmt in (16, 17, 20, 21, 70, 74, 76):  # R8G8, R16
            return 2
        if fmt in (37, 38, 41, 42, 43, 44, 50, 98, 99, 100, 124, 125, 126):  # RGBA8, R32
            return 4
        if fmt in (77, 83, 103, 128, 129):  # RG16, RG32, D16S8, D24S8
            return 4
        if fmt in (91, 95, 97, 130):  # RGBA16, D32S8
            return 8
        if fmt in (106,):  # RGB32F
            return 12
        if fmt in (109,):  # RGBA32F
            return 16
        
        # 默认假设 4 字节
        return 4
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        parts = [f"{self.type_name}:{self.dimensions}"]
        if self.msaa_desc:
            parts.append(self.msaa_desc)
        parts.append(self.format_name)
        return " ".join(parts)


@dataclass
class RDCFileInfo:
    """RDC 文件完整信息"""
    filepath: str
    file_size: int
    header: FileHeader
    thumbnail: Thumbnail
    metadata: CaptureMetaData
    time_base: Optional[TimeBase]
    sections: List[SectionInfo] = field(default_factory=list)
    
    @property
    def driver_name(self) -> str:
        return self.metadata.driver_name
    
    @property
    def is_vulkan(self) -> bool:
        return self.metadata.driver_id == RDCDriver.Vulkan
    
    @property
    def is_d3d11(self) -> bool:
        return self.metadata.driver_id == RDCDriver.D3D11
    
    @property
    def is_d3d12(self) -> bool:
        return self.metadata.driver_id == RDCDriver.D3D12
    
    @property
    def frame_capture_section(self) -> Optional[SectionInfo]:
        """获取 FrameCapture Section"""
        for section in self.sections:
            if section.section_type == SectionType.FrameCapture:
                return section
        return None
    
    @property
    def resource_renames_section(self) -> Optional[SectionInfo]:
        """获取 ResourceRenames Section（用户自定义资源名称）"""
        for section in self.sections:
            if section.section_type == SectionType.ResourceRenames:
                return section
        return None


# ============================================================================
# 解析器
# ============================================================================

class RDCParser:
    """RDC 文件解析器"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.file_size = os.path.getsize(filepath)
        self._file: Optional[BinaryIO] = None
        self._rdc_info: Optional[RDCFileInfo] = None
        self._frame_capture_data: Optional[bytes] = None
    
    def __enter__(self):
        self._file = open(self.filepath, 'rb')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()
            self._file = None
    
    def _read(self, size: int) -> bytes:
        """读取指定字节数"""
        data = self._file.read(size)
        if len(data) != size:
            raise EOFError(f"Expected {size} bytes, got {len(data)}")
        return data
    
    def _read_u8(self) -> int:
        return struct.unpack('<B', self._read(1))[0]
    
    def _read_u16(self) -> int:
        return struct.unpack('<H', self._read(2))[0]
    
    def _read_u32(self) -> int:
        return struct.unpack('<I', self._read(4))[0]
    
    def _read_u64(self) -> int:
        return struct.unpack('<Q', self._read(8))[0]
    
    def _read_f64(self) -> float:
        return struct.unpack('<d', self._read(8))[0]
    
    def _read_string(self, length: int) -> str:
        """读取固定长度字符串"""
        data = self._read(length)
        # 去除 null 终止符
        null_idx = data.find(b'\x00')
        if null_idx >= 0:
            data = data[:null_idx]
        return data.decode('utf-8', errors='replace')
    
    def _tell(self) -> int:
        return self._file.tell()
    
    def _seek(self, offset: int, whence: int = 0):
        self._file.seek(offset, whence)
    
    def _align_to(self, alignment: int):
        """对齐到指定边界"""
        pos = self._tell()
        aligned = (pos + alignment - 1) & ~(alignment - 1)
        if aligned > pos:
            self._seek(aligned)
    
    def parse_header(self) -> RDCFileInfo:
        """解析 RDC 文件头和元数据"""
        self._seek(0)
        
        # 1. FileHeader
        magic = self._read(8)[:4]  # 只取前4字节，后4字节是填充
        # 重新读取
        self._seek(0)
        magic = self._read(4)
        magic_padding = self._read(4)
        version = self._read_u32()
        header_length = self._read_u32()
        prog_version = self._read_string(16)
        
        file_header = FileHeader(
            magic=magic,
            version=version,
            header_length=header_length,
            prog_version=prog_version
        )
        
        if not file_header.is_valid:
            raise ValueError(f"Invalid RDC magic: {magic.hex()}, expected 'RDOC'")
        
        # 2. BinaryThumbnail
        thumb_width = self._read_u16()
        thumb_height = self._read_u16()
        thumb_length = self._read_u32()
        thumb_data = self._read(thumb_length) if thumb_length > 0 else b''
        
        thumbnail = Thumbnail(
            width=thumb_width,
            height=thumb_height,
            data=thumb_data
        )
        
        # 3. CaptureMetaData
        machine_ident = self._read_u64()
        driver_id_raw = self._read_u32()
        driver_name_length = self._read_u8()
        driver_name = self._read_string(driver_name_length)
        
        try:
            driver_id = RDCDriver(driver_id_raw)
        except ValueError:
            driver_id = RDCDriver.Unknown
        
        metadata = CaptureMetaData(
            machine_ident=machine_ident,
            driver_id=driver_id,
            driver_name=driver_name
        )
        
        # 4. TimeBase (v1.2+)
        time_base = None
        if version >= RDC_VERSION_1_2:
            tb = self._read_u64()
            tf = self._read_f64()
            time_base = TimeBase(time_base=tb, time_freq=tf)
        
        # 跳过到 header 结束
        current_pos = self._tell()
        if current_pos < header_length:
            self._seek(header_length)
        
        # 5. 解析 Sections
        sections = []
        while self._tell() < self.file_size:
            section = self._parse_section_header()
            if section is None:
                break
            sections.append(section)
            # 跳过 section 数据
            self._seek(section.data_offset + section.compressed_size)
        
        self._rdc_info = RDCFileInfo(
            filepath=self.filepath,
            file_size=self.file_size,
            header=file_header,
            thumbnail=thumbnail,
            metadata=metadata,
            time_base=time_base,
            sections=sections
        )
        
        return self._rdc_info
    
    def _parse_section_header(self) -> Optional[SectionInfo]:
        """解析单个 Section Header"""
        header_offset = self._tell()
        
        if header_offset >= self.file_size:
            return None
        
        # 读取第一个字节判断是 ASCII 还是 Binary
        is_ascii = self._read_u8()
        
        if is_ascii == ord('A'):
            # ASCII Section (不常用，简化处理)
            raise NotImplementedError("ASCII sections not supported")
        elif is_ascii != 0:
            raise ValueError(f"Invalid section marker: 0x{is_ascii:02x}")
        
        # Binary Section
        zero = self._read(3)  # 保留字节
        section_type_raw = self._read_u32()
        compressed_length = self._read_u64()
        uncompressed_length = self._read_u64()
        section_version = self._read_u64()
        section_flags_raw = self._read_u32()
        name_length = self._read_u32()
        
        if name_length == 0 or name_length > 2048:
            raise ValueError(f"Invalid section name length: {name_length}")
        
        name = self._read_string(name_length)
        
        try:
            section_type = SectionType(section_type_raw)
        except ValueError:
            section_type = SectionType.Unknown
        
        try:
            section_flags = SectionFlags(section_flags_raw)
        except ValueError:
            section_flags = SectionFlags.NoFlags
        
        data_offset = self._tell()
        
        return SectionInfo(
            section_type=section_type,
            name=name,
            compressed_size=compressed_length,
            uncompressed_size=uncompressed_length,
            version=section_version,
            flags=section_flags,
            data_offset=data_offset,
            header_offset=header_offset
        )
    
    def read_section_data(self, section: SectionInfo) -> bytes:
        """读取并解压 Section 数据"""
        self._seek(section.data_offset)
        compressed_data = self._read(section.compressed_size)
        
        if not section.is_compressed:
            return compressed_data
        
        # 解压
        if section.flags & SectionFlags.LZ4Compressed:
            return self._decompress_lz4_blocks(compressed_data, section.uncompressed_size)
        
        elif section.flags & SectionFlags.ZstdCompressed:
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                return dctx.decompress(compressed_data, max_output_size=section.uncompressed_size)
            except ImportError:
                raise ImportError("需要安装 zstandard 库: pip install zstandard")
        
        return compressed_data
    
    def _decompress_lz4_blocks(self, compressed_data: bytes, uncompressed_size: int) -> bytes:
        """
        解压 RenderDoc 的 LZ4 块格式
        
        格式说明 (来自 renderdoc/serialise/lz4io.cpp):
        - 数据被分成多个 1MB (lz4BlockSize = 1024*1024) 的块
        - 每个块: [int32 压缩大小] [压缩数据]
        - 使用 LZ4 streaming 模式压缩，需要保持字典上下文
        """
        try:
            import lz4.block
        except ImportError:
            raise ImportError("需要安装 lz4 库: pip install lz4")
        
        LZ4_BLOCK_SIZE = 1024 * 1024  # 1MB
        
        result = bytearray()
        offset = 0
        prev_block = b''  # 用于字典模式
        
        while offset < len(compressed_data):
            # 读取压缩块大小 (int32, little-endian)
            if offset + 4 > len(compressed_data):
                break
            
            comp_size = struct.unpack_from('<i', compressed_data, offset)[0]
            offset += 4
            
            if comp_size <= 0 or comp_size > len(compressed_data) - offset:
                break
            
            # 读取压缩数据
            comp_block = compressed_data[offset:offset + comp_size]
            offset += comp_size
            
            # 解压块（使用前一个块作为字典）
            try:
                if prev_block:
                    # LZ4 streaming 模式需要前一个解压块作为字典
                    decompressed = lz4.block.decompress(
                        comp_block,
                        uncompressed_size=LZ4_BLOCK_SIZE,
                        dict=prev_block
                    )
                else:
                    decompressed = lz4.block.decompress(
                        comp_block,
                        uncompressed_size=LZ4_BLOCK_SIZE
                    )
            except lz4.block.LZ4BlockError as e:
                # 可能是最后一个小块
                try:
                    decompressed = lz4.block.decompress(comp_block)
                except:
                    print(f"Warning: LZ4 decompression failed at offset {offset}: {e}")
                    break
            
            result.extend(decompressed)
            prev_block = bytes(decompressed)  # 保存用于下一个块的字典
            
            # 检查是否已达到预期大小
            if len(result) >= uncompressed_size:
                break
        
        return bytes(result[:uncompressed_size])
    
    def get_frame_capture_data(self) -> bytes:
        """获取解压后的 FrameCapture 数据"""
        if self._frame_capture_data is not None:
            return self._frame_capture_data
        
        if self._rdc_info is None:
            self.parse_header()
        
        fc_section = self._rdc_info.frame_capture_section
        if fc_section is None:
            raise ValueError("No FrameCapture section found")
        
        self._frame_capture_data = self.read_section_data(fc_section)
        return self._frame_capture_data
    
    def parse_resource_renames(self) -> Dict[int, str]:
        """
        解析 ResourceRenames Section，返回 ResourceID -> 用户自定义名称 的映射
        
        RenderDoc UI 允许用户为资源设置自定义名称（右键 -> Set Custom Name）。
        这些名称存储在 RDC 文件的 ResourceRenames section 中，格式为 JSON：
        
        {
          "CustomResourceNames": {
            "ResourceId::119808": "MyTexture",
            "ResourceId::123456": "ShadowMap"
          }
        }
        
        Returns:
            Dict[int, str]: ResourceID (整数) -> 自定义名称 的映射
                           如果该 section 不存在，返回空字典
        """
        if self._rdc_info is None:
            self.parse_header()
        
        renames_section = self._rdc_info.resource_renames_section
        if renames_section is None:
            return {}
        
        try:
            # 读取并解压 section 数据
            data = self.read_section_data(renames_section)
            
            # 解析 JSON（UTF-8 编码）
            json_str = data.decode('utf-8')
            root = json.loads(json_str)
            
            # 提取 CustomResourceNames
            renames = {}
            if 'CustomResourceNames' in root:
                custom_names = root['CustomResourceNames']
                for key, value in custom_names.items():
                    # key 格式: "ResourceId::119808"
                    if key.startswith('ResourceId::'):
                        try:
                            resource_id = int(key[len('ResourceId::'):])
                            renames[resource_id] = value
                        except ValueError:
                            pass
            
            return renames
            
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to parse ResourceRenames section: {e}")
            return {}
    
    def parse_chunks(self, data: bytes) -> List[ChunkInfo]:
        """解析 FrameCapture 中的所有 Chunks"""
        chunks = []
        offset = 0
        max_invalid = 100  # 允许连续跳过的无效对齐填充
        invalid_count = 0
        
        while offset < len(data) - 4:
            # 跳过对齐填充（全零）
            while offset < len(data) - 4:
                test = struct.unpack_from('<I', data, offset)[0]
                if test != 0:
                    break
                offset += 4
                invalid_count += 1
                if invalid_count > max_invalid:
                    # 达到大块零填充区域，尝试对齐跳过
                    offset = ((offset + CHUNK_ALIGNMENT - 1) // CHUNK_ALIGNMENT) * CHUNK_ALIGNMENT
                    invalid_count = 0
            
            if offset >= len(data) - 4:
                break
            
            chunk, new_offset = self._parse_chunk_header(data, offset)
            if chunk is None:
                # 跳到下一个对齐边界重试
                offset = ((offset + CHUNK_ALIGNMENT) // CHUNK_ALIGNMENT) * CHUNK_ALIGNMENT
                invalid_count += 1
                if invalid_count > max_invalid:
                    break
                continue
            
            invalid_count = 0
            chunks.append(chunk)
            
            # 移动到下一个 chunk：数据结束后对齐到 64 字节
            next_offset = chunk.data_offset + chunk.length
            offset = ((next_offset + CHUNK_ALIGNMENT - 1) // CHUNK_ALIGNMENT) * CHUNK_ALIGNMENT
        
        return chunks
    
    def _parse_chunk_header(self, data: bytes, offset: int) -> Tuple[Optional[ChunkInfo], int]:
        """解析单个 Chunk Header"""
        if offset + 4 > len(data):
            return None, offset
        
        # 读取 chunk type + flags
        c = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        if c == 0:  # Chunk 0 是无效的
            return None, offset
        
        chunk_id = c & CHUNK_INDEX_MASK
        flags = c & ~CHUNK_INDEX_MASK
        
        # 可选字段
        callstack = None
        thread_id = None
        duration_micro = None
        timestamp_micro = None
        
        if flags & CHUNK_CALLSTACK:
            num_frames = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            if num_frames < 4096:
                callstack = list(struct.unpack_from(f'<{num_frames}Q', data, offset))
                offset += num_frames * 8
            else:
                offset += num_frames * 8  # 跳过
        
        if flags & CHUNK_THREAD_ID:
            thread_id = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
        
        if flags & CHUNK_DURATION:
            duration_micro = struct.unpack_from('<q', data, offset)[0]
            offset += 8
        
        if flags & CHUNK_TIMESTAMP:
            timestamp_micro = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
        
        # Chunk 长度
        if flags & CHUNK_64BIT_SIZE:
            length = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
        else:
            length = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        
        chunk = ChunkInfo(
            chunk_id=chunk_id,
            flags=flags,
            length=length,
            data_offset=offset,
            thread_id=thread_id,
            duration_micro=duration_micro,
            timestamp_micro=timestamp_micro,
            callstack=callstack
        )
        
        return chunk, offset
    
    def extract_vulkan_shaders(self) -> List[ShaderInfo]:
        """提取所有 Vulkan Shader (SPIR-V)"""
        if self._rdc_info is None:
            self.parse_header()
        
        if not self._rdc_info.is_vulkan:
            raise ValueError(f"Not a Vulkan capture: {self._rdc_info.driver_name}")
        
        fc_data = self.get_frame_capture_data()
        chunks = self.parse_chunks(fc_data)
        
        shaders = []
        for chunk in chunks:
            if chunk.chunk_id == VulkanChunk.vkCreateShaderModule:
                shader = self._extract_shader_from_chunk(fc_data, chunk)
                if shader and shader.is_valid_spirv:
                    shaders.append(shader)
        
        return shaders
    
    def _extract_shader_from_chunk(self, data: bytes, chunk: ChunkInfo) -> Optional[ShaderInfo]:
        """从 vkCreateShaderModule chunk 中提取 Shader
        
        数据结构 (基于调试分析):
        - offset 0x00-0x07: ResourceId (device)
        - offset 0x08-0x0F: 标志或其他数据
        - offset 0x10-0x17: codeSize (uint64_t)
        - offset 0x18-0x1F: 重复的 codeSize
        - offset 0x20-0x5F: 填充 (全零)
        - offset 0x60+: SPIR-V 数据 (64字节对齐)
        """
        try:
            offset = chunk.data_offset
            chunk_end = offset + chunk.length
            
            if chunk.length < 0x64:  # 最小有效长度
                return None
            
            # 读取 ResourceId (偏移 0x00)
            resource_id = struct.unpack_from('<Q', data, offset)[0]
            
            # 读取 codeSize (偏移 0x10)
            code_size = struct.unpack_from('<Q', data, offset + 0x10)[0]
            
            # 验证 codeSize
            if code_size == 0 or code_size > chunk.length or code_size % 4 != 0:
                # 尝试备用方法：直接搜索 SPIR-V magic
                spirv_offset = self._find_spirv_in_chunk(data, offset, chunk_end)
                if spirv_offset < 0:
                    return None
                spirv_data = self._extract_spirv_blob(data, spirv_offset, chunk_end)
                if spirv_data:
                    return ShaderInfo(
                        resource_id=resource_id,
                        spirv_data=spirv_data,
                        code_size=len(spirv_data),
                        chunk_offset=chunk.data_offset
                    )
                return None
            
            # SPIR-V 数据在 0x60 偏移处 (64字节对齐)
            spirv_offset = offset + 0x60
            
            # 验证 SPIR-V magic
            if spirv_offset + 4 > chunk_end:
                return None
            
            magic = struct.unpack_from('<I', data, spirv_offset)[0]
            if magic != SPIRV_MAGIC:
                # Magic 不在预期位置，搜索
                spirv_offset = self._find_spirv_in_chunk(data, offset, chunk_end)
                if spirv_offset < 0:
                    return None
            
            # 提取 SPIR-V 数据
            spirv_end = spirv_offset + code_size
            if spirv_end > chunk_end:
                # codeSize 超出 chunk 范围，使用 chunk 剩余长度
                spirv_end = chunk_end
                code_size = spirv_end - spirv_offset
            
            spirv_data = data[spirv_offset:spirv_end]
            
            # 验证提取的数据
            if len(spirv_data) < 20:  # SPIR-V header 最小 20 字节
                return None
            
            # 确保 magic 正确
            extracted_magic = struct.unpack_from('<I', spirv_data, 0)[0]
            if extracted_magic != SPIRV_MAGIC:
                return None
            
            return ShaderInfo(
                resource_id=resource_id,
                spirv_data=spirv_data,
                code_size=code_size,
                chunk_offset=chunk.data_offset
            )
            
        except Exception as e:
            print(f"Warning: Failed to extract shader from chunk at {chunk.data_offset}: {e}")
            return None
    
    def _find_spirv_in_chunk(self, data: bytes, start: int, end: int) -> int:
        """在 chunk 数据中搜索 SPIR-V magic"""
        magic_bytes = struct.pack('<I', SPIRV_MAGIC)
        
        # 只在 64 字节对齐的位置搜索
        aligned_start = (start + CHUNK_ALIGNMENT - 1) & ~(CHUNK_ALIGNMENT - 1)
        
        pos = aligned_start
        while pos < end - 4:
            if data[pos:pos+4] == magic_bytes:
                return pos
            pos += CHUNK_ALIGNMENT
        
        # 如果对齐搜索失败，尝试任意位置
        idx = data.find(magic_bytes, start, end)
        return idx
    
    def _extract_spirv_blob(self, data: bytes, start: int, max_end: int) -> Optional[bytes]:
        """提取 SPIR-V blob，基于 SPIR-V 结构"""
        if start + 20 > max_end:
            return None
        
        # SPIR-V header: magic(4) + version(4) + generator(4) + bound(4) + reserved(4)
        magic, version, generator, bound, reserved = struct.unpack_from('<5I', data, start)
        
        if magic != SPIRV_MAGIC:
            return None
        
        # SPIR-V 是 word (4 bytes) 为单位
        # 扫描直到遇到无效指令或超出范围
        offset = start + 20  # 跳过 header
        
        while offset < max_end - 4:
            word = struct.unpack_from('<I', data, offset)[0]
            word_count = word >> 16
            opcode = word & 0xFFFF
            
            if word_count == 0:
                break
            
            if opcode == 0 and word_count == 0:
                break
            
            offset += word_count * 4
        
        # 返回 SPIR-V 数据
        size = offset - start
        if size > 0 and size % 4 == 0:
            return data[start:offset]
        
        return None
    
    def extract_vulkan_textures(self) -> List[TextureInfo]:
        """提取所有 Vulkan 纹理（Image）元数据
        
        解析 vkCreateImage chunk 获取 VkImageCreateInfo 信息。
        注意：这只提取元数据，不提取实际像素数据（需要 GPU 回放）。
        """
        if self._rdc_info is None:
            self.parse_header()
        
        if not self._rdc_info.is_vulkan:
            raise ValueError(f"Not a Vulkan capture: {self._rdc_info.driver_name}")
        
        fc_data = self.get_frame_capture_data()
        chunks = self.parse_chunks(fc_data)
        
        textures = []
        for chunk in chunks:
            if chunk.chunk_id == VulkanChunk.vkCreateImage:
                texture = self._extract_texture_from_chunk(fc_data, chunk)
                if texture:
                    textures.append(texture)
        
        return textures
    
    def _extract_texture_from_chunk(self, data: bytes, chunk: ChunkInfo) -> Optional[TextureInfo]:
        """从 vkCreateImage chunk 中提取纹理元数据
        
        基于实际 RDC 数据分析的布局:
        
        短格式 (106 bytes):
        - 0x00-0x07: Device ResourceId (8 bytes)
        - 0x08-0x0B: 标记 = 14 (0x0E)
        - 0x0C-0x0F: flags (uint32)
        - 0x10: 额外字节 (0x00)
        - 0x11-0x14: imageType (注意: 偏移了1字节!)
        - ...
        
        长格式 (136 bytes, 包含 pNext 链):
        - 包含额外的扩展信息
        
        由于字节对齐问题，我们直接搜索特征模式。
        """
        try:
            offset = chunk.data_offset
            chunk_end = offset + chunk.length
            
            if chunk.length < 64:
                return None
            
            # 读取 device ResourceId
            device_id = struct.unpack_from('<Q', data, offset)[0]
            
            # 从偏移 0x08 开始搜索数据
            # 跳过 device ResourceId 和标记
            search_start = offset + 8
            
            # 基于实际数据分析，有两种格式：
            # 1. 短格式 (106 bytes): 标记后直接是 VkImageCreateInfo
            # 2. 长格式 (136 bytes): 标记后有 pNext 扩展数据
            
            # 读取标记
            marker = struct.unpack_from('<I', data, search_start)[0]
            
            if marker == 14:  # 简单格式
                # 短格式布局 (基于 hex dump 分析):
                # 0x08: 0e000000 (marker=14)
                # 0x0C: 00000000 (flags)
                # 0x10: 00       (padding byte?)
                # 0x11: 01000000 (imageType - 但这是错误对齐!)
                
                # 实际上，RenderDoc 可能使用不同的对齐。让我尝试两种方式:
                
                # 方式 1: 假设在 0x0C 是 flags，然后每 4 字节
                texture = self._parse_format_a(data, offset, chunk_end)
                if texture:
                    return texture
                
                # 方式 2: 假设字节对齐问题，从 0x11 开始
                texture = self._parse_format_b(data, offset, chunk_end)
                if texture:
                    return texture
            
            else:
                # 长格式，包含 pNext 链，需要不同解析
                texture = self._parse_format_c(data, offset, chunk_end)
                if texture:
                    return texture
            
            # 备用：通用扫描
            return self._try_parse_image_create_info(data, search_start, chunk_end, chunk.data_offset)
            
        except Exception as e:
            return None
    
    def _parse_format_a(self, data: bytes, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """解析格式 A：标准对齐"""
        try:
            # 基于 Chunk 2 hex dump:
            # 0000: 0b 01 00 00 00 00 00 00 (device = 0x10B)
            # 0008: 0e 00 00 00 (marker = 14)
            # 000C: 00 20 00 00 (flags = 0x2000)
            # 0010: 00 02 00 00 (imageType << 8 | something? = 512)
            
            # 这看起来是错误的对齐。让我尝试另一种解释:
            # 可能 flags 是 0, 然后下一个字节是 padding
            
            offset = chunk_start + 12  # 跳过 device(8) + marker(4)
            
            # 读取 flags (4 bytes)
            flags = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            # 检查是否有额外的 1 字节 padding
            # 如果下一个字节是 0x00 且后面是 0x01 或 0x02，说明有 padding
            if offset < chunk_end - 1:
                b0 = data[offset]
                b1 = data[offset + 1] if offset + 1 < chunk_end else 0
                
                if b0 == 0 and b1 in (0, 1, 2):
                    # 有 1 字节 padding
                    offset += 1
            
            # 现在读取 imageType
            image_type = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            if image_type > 2:
                return None
            
            # format
            fmt = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            if fmt == 0 or fmt > 300:
                return None
            
            # extent: width, height, depth
            width = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            height = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            depth = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            if width == 0 or width > 16384:
                return None
            if height == 0 or height > 16384:
                return None
            if depth == 0 or depth > 2048:
                return None
            
            # mipLevels, arrayLayers, samples, tiling, usage
            mip_levels = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            array_layers = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            samples = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            tiling = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            usage = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            # 验证
            if mip_levels == 0 or mip_levels > 15:
                return None
            if array_layers == 0 or array_layers > 2048:
                return None
            if samples not in (1, 2, 4, 8, 16, 32, 64):
                return None
            if tiling > 1:
                return None
            if usage == 0 or usage > 0xFFFF:
                return None
            
            # 读取 Image ResourceId（在 VkImageCreateInfo 之后）
            # 搜索 padding 后的 ResourceId
            resource_id = 0
            search_start = offset
            for skip in range(0, min(32, chunk_end - search_start - 8), 4):
                rid = struct.unpack_from('<Q', data, search_start + skip)[0]
                if 0 < rid < (1 << 48):
                    resource_id = rid
                    break
            
            return TextureInfo(
                resource_id=resource_id,
                image_type=image_type,
                format=fmt,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mip_levels,
                array_layers=array_layers,
                samples=samples,
                usage=usage,
                chunk_offset=chunk_start
            )
            
        except (struct.error, IndexError):
            return None
    
    def _parse_format_b(self, data: bytes, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """解析格式 B：短格式 (106 bytes)，带 1 字节 padding
        
        验证通过的布局 (基于 debug_image_detailed.py 分析):
        - 0x00-0x07: Device ResourceId (8 bytes)
        - 0x08-0x0B: Marker = 14 (4 bytes)
        - 0x0C-0x0F: flags (4 bytes)
        - 0x10: padding byte (1 byte, 值为 0x00)
        - 0x11-0x14: imageType (4 bytes)
        - 0x15-0x18: format (4 bytes)
        - 0x19-0x1C: width (4 bytes)
        - 0x1D-0x20: height (4 bytes)
        - 0x21-0x24: depth (4 bytes)
        - 0x25-0x28: mipLevels (4 bytes)
        - 0x29-0x2C: arrayLayers (4 bytes)
        - 0x2D-0x30: samples (4 bytes)
        - 0x31-0x34: tiling (4 bytes)
        - 0x35-0x38: usage (4 bytes)
        - 然后是 Image ResourceId
        """
        try:
            # 先检查 chunk 长度是否匹配短格式
            chunk_len = chunk_end - chunk_start
            if chunk_len != 106:
                return None
            
            # 检查 padding byte
            padding = data[chunk_start + 0x10]
            if padding != 0:
                return None  # 这不是短格式
            
            # 从偏移 0x11 开始读取 VkImageCreateInfo 字段
            offset = chunk_start + 0x11
            
            if offset + 40 > chunk_end:
                return None
            
            image_type = struct.unpack_from('<I', data, offset)[0]
            if image_type > 2:
                return None
            offset += 4
            
            fmt = struct.unpack_from('<I', data, offset)[0]
            if fmt == 0 or fmt > 300:
                return None
            offset += 4
            
            width = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            height = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            depth = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            if width == 0 or height == 0 or depth == 0:
                return None
            if width > 16384 or height > 16384 or depth > 2048:
                return None
            
            mip_levels = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            array_layers = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            samples = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            tiling = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            usage = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            if mip_levels == 0 or mip_levels > 15:
                return None
            if array_layers == 0 or array_layers > 2048:
                return None
            if samples not in (1, 2, 4, 8, 16, 32, 64):
                return None
            if tiling > 1:
                return None
            if usage == 0 or usage > 0xFFFF:
                return None
            
            # 读取 Image ResourceId (在 offset 0x54 附近)
            # 根据 hex dump，ResourceId 在 0x54 (84) 位置
            resource_id = 0
            rid_offset = chunk_start + 0x54
            if rid_offset + 8 <= chunk_end:
                resource_id = struct.unpack_from('<Q', data, rid_offset)[0]
            
            return TextureInfo(
                resource_id=resource_id,
                image_type=image_type,
                format=fmt,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mip_levels,
                array_layers=array_layers,
                samples=samples,
                usage=usage,
                chunk_offset=chunk_start
            )
            
        except (struct.error, IndexError):
            return None
    
    def _parse_format_c(self, data: bytes, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """解析格式 C：带 pNext 扩展的长格式 (136 bytes)
        
        基于 hex 分析的布局（含 pNext 扩展块）:
        - 0x00-0x07: Device ResourceId (8 bytes)
        - 0x08-0x0B: Marker = 14 (4 bytes)
        - 0x0C-0x0F: flags (4 bytes)
        - 0x10: pNext presence marker (1 byte, 值为 0x01)
        - 0x11-0x20: pNext 扩展数据 (16 bytes)
        - 0x21-0x22: 更多 pNext 数据 (2 bytes)
        - 0x23: padding byte (1 byte, 值为 0x00)
        - 0x24-0x27: format (4 bytes)  <- 关键偏移！
        - 0x28-0x2B: width (4 bytes)   <- 调整后
        - 0x2C-0x2F: height (4 bytes)  <- 调整后
        - 0x30-0x33: depth (4 bytes)
        - 0x34-0x37: mipLevels (4 bytes)
        - 0x38-0x3B: arrayLayers (4 bytes)
        - 0x3C-0x3F: samples (4 bytes)
        - 0x40-0x43: tiling (4 bytes)
        - 0x44-0x47: usage (4 bytes)
        - 后续是 sharingMode, queueFamilyIndices, initialLayout, Image ResourceId
        
        注意：format 和 extent 的偏移可能因 pNext 内容不同而有微小变化。
        下面使用两种策略：固定偏移 + 特征扫描作为后备。
        """
        try:
            # 先检查 chunk 长度是否匹配长格式
            chunk_len = chunk_end - chunk_start
            if chunk_len < 120 or chunk_len > 160:
                return None  # 不在长格式范围内
            
            # 检查 pNext 标记 (0x10 处应该是 0x01 表示有 pNext)
            pnext_marker = data[chunk_start + 0x10]
            if pnext_marker != 0x01:
                return None  # 这不是带 pNext 的长格式
            
            # 策略 1：尝试固定偏移解析
            result = self._try_format_c_fixed_offset(data, chunk_start, chunk_end)
            if result:
                return result
            
            # 策略 2：扫描查找 format + extent 模式
            result = self._try_format_c_scan(data, chunk_start, chunk_end)
            if result:
                return result
            
            return None
            
        except (struct.error, IndexError):
            return None
    
    def _try_format_c_fixed_offset(self, data: bytes, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """尝试使用固定偏移解析长格式 vkCreateImage"""
        try:
            # 基于 hex 分析，format 在 0x24，extent 紧随其后
            # 但需要考虑可能的变体，尝试几个常见偏移
            offset_candidates = [
                # (format_offset, description)
                (0x24, "标准 pNext 长格式"),
                (0x23, "无额外 padding"),
                (0x25, "多一字节 padding"),
            ]
            
            for fmt_offset, desc in offset_candidates:
                result = self._parse_at_offset(data, chunk_start, chunk_end, fmt_offset)
                if result:
                    return result
            
            return None
            
        except (struct.error, IndexError):
            return None
    
    def _parse_at_offset(self, data: bytes, chunk_start: int, chunk_end: int, fmt_offset: int) -> Optional[TextureInfo]:
        """从指定偏移解析 VkImageCreateInfo 结构"""
        try:
            base = chunk_start + fmt_offset
            if base + 40 > chunk_end:
                return None
            
            # 读取 format, extent (w, h, d), mipLevels, arrayLayers, samples, tiling, usage
            # 注意：这里假设 imageType 在 format 之前，但长格式可能不同
            # 先尝试直接读取 format 开始的序列
            
            fmt = struct.unpack_from('<I', data, base)[0]
            if fmt == 0 or fmt > 300:
                return None
            
            width = struct.unpack_from('<I', data, base + 4)[0]
            height = struct.unpack_from('<I', data, base + 8)[0]
            depth = struct.unpack_from('<I', data, base + 12)[0]
            
            if width == 0 or height == 0 or depth == 0:
                return None
            if width > 16384 or height > 16384 or depth > 2048:
                return None
            
            mip_levels = struct.unpack_from('<I', data, base + 16)[0]
            array_layers = struct.unpack_from('<I', data, base + 20)[0]
            samples = struct.unpack_from('<I', data, base + 24)[0]
            tiling = struct.unpack_from('<I', data, base + 28)[0]
            usage = struct.unpack_from('<I', data, base + 32)[0]
            
            # 验证字段
            if mip_levels == 0 or mip_levels > 15:
                return None
            if array_layers == 0 or array_layers > 2048:
                return None
            if samples not in (1, 2, 4, 8, 16, 32, 64):
                return None
            if tiling > 1:
                return None
            if usage == 0 or usage > 0xFFFF:
                return None
            
            # 长格式中 imageType 在更早的位置，尝试读取
            # 根据布局，imageType 可能在 0x20 或其他位置
            image_type = 1  # 默认 2D
            for type_offset in [0x20, 0x21, 0x22, 0x23]:
                if chunk_start + type_offset < base:
                    candidate = struct.unpack_from('<I', data, chunk_start + type_offset)[0]
                    if candidate <= 2:
                        image_type = candidate
                        break
            
            # 读取 Image ResourceId (通常在 chunk 尾部)
            resource_id = 0
            # 长格式的 ResourceId 位置不同，尝试从尾部向前搜索
            for rid_offset in range(-16, -4):
                try:
                    rid = struct.unpack_from('<Q', data, chunk_end + rid_offset)[0]
                    if 0 < rid < 0xFFFFFFFF:  # 合理的 ResourceId 范围
                        resource_id = rid
                        break
                except:
                    pass
            
            return TextureInfo(
                resource_id=resource_id,
                image_type=image_type,
                format=fmt,
                width=width,
                height=height,
                depth=depth,
                mip_levels=mip_levels,
                array_layers=array_layers,
                samples=samples,
                usage=usage,
                chunk_offset=chunk_start
            )
            
        except (struct.error, IndexError):
            return None
    
    def _try_format_c_scan(self, data: bytes, chunk_start: int, chunk_end: int) -> Optional[TextureInfo]:
        """通过特征扫描查找长格式中的 format + extent"""
        try:
            chunk_len = chunk_end - chunk_start
            best_result = None
            best_score = 0
            
            # 扫描可能的 format 起始位置 (0x20 - 0x40 范围)
            for scan_offset in range(0x20, min(0x50, chunk_len - 36), 1):
                pos = chunk_start + scan_offset
                
                try:
                    fmt = struct.unpack_from('<I', data, pos)[0]
                    if fmt == 0 or fmt > 300:
                        continue
                    
                    width = struct.unpack_from('<I', data, pos + 4)[0]
                    height = struct.unpack_from('<I', data, pos + 8)[0]
                    depth = struct.unpack_from('<I', data, pos + 12)[0]
                    
                    if width == 0 or height == 0 or depth == 0:
                        continue
                    if width > 16384 or height > 16384 or depth > 2048:
                        continue
                    
                    # 计算匹配分数
                    score = 10
                    
                    # 已知格式加分
                    if fmt in VK_FORMAT_NAMES:
                        score += 10
                    
                    # 2 的幂次尺寸加分
                    if width > 0 and (width & (width - 1)) == 0:
                        score += 3
                    if height > 0 and (height & (height - 1)) == 0:
                        score += 3
                    
                    # 验证后续字段
                    mip = struct.unpack_from('<I', data, pos + 16)[0]
                    layers = struct.unpack_from('<I', data, pos + 20)[0]
                    samples = struct.unpack_from('<I', data, pos + 24)[0]
                    
                    if 0 < mip <= 15:
                        score += 2
                    else:
                        continue
                    
                    if 0 < layers <= 2048:
                        score += 2
                    else:
                        continue
                    
                    if samples in (1, 2, 4, 8, 16, 32, 64):
                        score += 3
                    else:
                        continue
                    
                    if score > best_score:
                        best_score = score
                        
                        tiling = struct.unpack_from('<I', data, pos + 28)[0]
                        usage = struct.unpack_from('<I', data, pos + 32)[0]
                        
                        # 获取 ResourceId
                        resource_id = 0
                        for rid_offset in range(-16, -4):
                            try:
                                rid = struct.unpack_from('<Q', data, chunk_end + rid_offset)[0]
                                if 0 < rid < 0xFFFFFFFF:
                                    resource_id = rid
                                    break
                            except:
                                pass
                        
                        best_result = TextureInfo(
                            resource_id=resource_id,
                            image_type=1,  # 假设 2D
                            format=fmt,
                            width=width,
                            height=height,
                            depth=depth,
                            mip_levels=mip,
                            array_layers=layers,
                            samples=samples,
                            usage=usage if usage <= 0xFFFF else 0,
                            chunk_offset=chunk_start
                        )
                        
                except (struct.error, IndexError):
                    continue
            
            return best_result
            
        except (struct.error, IndexError):
            return None
    
    def _try_parse_image_create_info(self, data: bytes, offset: int, chunk_end: int, chunk_offset: int) -> Optional[TextureInfo]:
        """尝试解析 VkImageCreateInfo 结构
        
        基于调试分析的 RenderDoc 实际布局:
        
        Chunk 数据（以 Chunk 4 为例，106 bytes）:
        0000: 0b01000000000000  - device ResourceId (8 bytes) = 0x10B
        0008: 0e000000          - 可能是序列化标记
        000C: 00000000          - flags = 0
        0010: 00                - imageType = 0 (2D)
        ...后续字段
        
        但从 hex dump 来看，格式更像是：
        offset 0x10: 00200000 = flags?
        offset 0x14: 00020000 = imageType=2 (VK_IMAGE_TYPE_2D=1)? 不对
        offset 0x18: 2c000000 = 44 (format?)
        
        让我尝试另一种解析方式：基于搜索特征值
        """
        if offset + 48 > chunk_end:
            return None
        
        # 方案：在 chunk 数据中搜索合理的 (imageType, format, extent) 模式
        # imageType 应该是 0, 1, 2 之一
        # format 应该是 1-200 左右（常见格式）
        # width/height 应该是 2 的幂次或合理的尺寸
        
        best_match = None
        best_score = 0
        
        # 扫描整个 chunk 寻找最佳匹配
        for scan_offset in range(0, min(80, chunk_end - offset - 44), 4):
            pos = offset + scan_offset
            
            try:
                # 尝试读取字段序列
                # RenderDoc 可能的布局：
                # [flags(4)] [imageType(4)] [format(4)] [width(4)] [height(4)] [depth(4)]
                # [mipLevels(4)] [arrayLayers(4)] [samples(4)] [tiling(4)] [usage(4)]
                
                vals = struct.unpack_from('<11I', data, pos)
                flags, image_type, fmt, width, height, depth, mip_levels, array_layers, samples, tiling, usage = vals
                
                # 计算匹配分数
                score = 0
                
                # imageType 必须是 0, 1, 2
                if image_type > 2:
                    continue
                score += 10
                
                # format 必须在合理范围
                if fmt == 0 or fmt > 500:
                    continue
                if fmt in VK_FORMAT_NAMES:
                    score += 5  # 已知格式加分
                else:
                    score += 1
                
                # extent 验证
                if width == 0 or width > 16384:
                    continue
                if height == 0 or height > 16384:
                    continue
                if depth == 0 or depth > 2048:
                    continue
                
                # 尺寸是 2 的幂次加分
                if (width & (width - 1)) == 0:
                    score += 2
                if (height & (height - 1)) == 0:
                    score += 2
                
                score += 5  # 基础分
                
                # mipLevels/arrayLayers 验证
                if mip_levels == 0 or mip_levels > 15:
                    continue
                if array_layers == 0 or array_layers > 2048:
                    continue
                score += 3
                
                # samples 必须是有效值
                if samples not in (1, 2, 4, 8, 16, 32, 64):
                    continue
                score += 3
                
                # tiling 只能是 0 或 1
                if tiling > 1:
                    continue
                score += 2
                
                # usage 验证
                if usage == 0 or usage > 0xFFFF:
                    continue
                score += 2
                
                # 额外验证：如果是 2D 纹理且 depth != 1，可能解析错误
                if image_type == 1 and depth != 1:
                    score -= 5
                
                # 如果是 1D 纹理且 height/depth != 1，可能解析错误
                if image_type == 0 and (height != 1 or depth != 1):
                    score -= 5
                
                if score > best_score:
                    best_score = score
                    
                    # 尝试找到 Image ResourceId
                    resource_id = 0
                    search_start = pos + 44
                    for rid_offset in range(0, min(32, chunk_end - search_start - 8), 4):
                        potential_rid = struct.unpack_from('<Q', data, search_start + rid_offset)[0]
                        if 0 < potential_rid < (1 << 48):
                            resource_id = potential_rid
                            break
                    
                    best_match = TextureInfo(
                        resource_id=resource_id,
                        image_type=image_type,
                        format=fmt,
                        width=width,
                        height=height,
                        depth=depth,
                        mip_levels=mip_levels,
                        array_layers=array_layers,
                        samples=samples,
                        usage=usage,
                        chunk_offset=chunk_offset
                    )
                    
            except struct.error:
                continue
        
        # 只返回高置信度的匹配
        if best_score >= 20:
            return best_match
        
        return None
    
    # ========================================================================
    # Draw Event 上下文解析
    # ========================================================================
    
    def extract_draw_events(self) -> Tuple[List[DrawEventContext], Dict[int, PipelineInfo]]:
        """提取所有 Draw/Dispatch 事件及其上下文信息
        
        遍历 FrameCapture 中的所有 Chunk，追踪：
        1. Debug Marker 的 Push/Pop（构建 marker_stack）
        2. vkCmdBindPipeline（追踪当前绑定的 Pipeline）
        3. vkCmdDraw/vkCmdDispatch 等绘制调用
        
        Returns:
            (draw_events, pipelines) 元组:
            - draw_events: 所有 Draw/Dispatch 事件列表
            - pipelines: ResourceId -> PipelineInfo 映射
        """
        if self._rdc_info is None:
            self.parse_header()
        
        if not self._rdc_info.is_vulkan:
            raise ValueError(f"Not a Vulkan capture: {self._rdc_info.driver_name}")
        
        fc_data = self.get_frame_capture_data()
        chunks = self.parse_chunks(fc_data)
        
        # 第一遍：收集所有 ShaderModule ResourceIds
        shader_module_ids: Dict[int, int] = {}  # resource_id -> chunk_index
        for idx, chunk in enumerate(chunks):
            if chunk.chunk_id == VulkanChunk.vkCreateShaderModule:
                chunk_end = chunk.data_offset + chunk.length
                if chunk.length >= 8:
                    rid = struct.unpack_from('<Q', fc_data, chunk_end - 8)[0]
                    if 0 < rid < (1 << 48):
                        shader_module_ids[rid] = idx
        
        draw_events: List[DrawEventContext] = []
        pipelines: Dict[int, PipelineInfo] = {}
        
        # 状态追踪
        current_marker_stack: List[str] = []
        current_graphics_pipeline: int = 0
        current_compute_pipeline: int = 0
        
        # 第二遍：处理所有事件
        for idx, chunk in enumerate(chunks):
            chunk_id = chunk.chunk_id
            
            # 处理 Debug Marker
            if chunk_id in MARKER_BEGIN_CHUNK_IDS:
                marker_name = self._parse_marker_begin(fc_data, chunk)
                if marker_name:
                    current_marker_stack.append(marker_name)
            
            elif chunk_id in MARKER_END_CHUNK_IDS:
                if current_marker_stack:
                    current_marker_stack.pop()
            
            # 处理 BindPipeline
            elif chunk_id == VulkanChunk.vkCmdBindPipeline:
                bind_point, pipeline_id = self._parse_bind_pipeline(fc_data, chunk)
                if bind_point == 0:  # VK_PIPELINE_BIND_POINT_GRAPHICS
                    current_graphics_pipeline = pipeline_id
                elif bind_point == 1:  # VK_PIPELINE_BIND_POINT_COMPUTE
                    current_compute_pipeline = pipeline_id
            
            # 处理 Draw 调用
            elif chunk_id in DRAW_CHUNK_IDS:
                event_type = self._get_draw_event_type(chunk_id)
                event = DrawEventContext(
                    chunk_index=idx,
                    chunk_id=chunk_id,
                    event_type=event_type,
                    pipeline_resource_id=current_graphics_pipeline,
                    marker_stack=list(current_marker_stack)  # 复制当前栈
                )
                draw_events.append(event)
            
            # 处理 Dispatch 调用
            elif chunk_id in DISPATCH_CHUNK_IDS:
                event_type = 'dispatch' if chunk_id == VulkanChunk.vkCmdDispatch else 'dispatch_indirect'
                event = DrawEventContext(
                    chunk_index=idx,
                    chunk_id=chunk_id,
                    event_type=event_type,
                    pipeline_resource_id=current_compute_pipeline,
                    marker_stack=list(current_marker_stack)
                )
                draw_events.append(event)
            
            # 处理 Pipeline 创建（建立 Pipeline -> Shader 映射）
            elif chunk_id == VulkanChunk.vkCreateGraphicsPipelines:
                pipeline_info = self._parse_graphics_pipeline(fc_data, chunk, shader_module_ids)
                if pipeline_info:
                    pipelines[pipeline_info.resource_id] = pipeline_info
            
            elif chunk_id == VulkanChunk.vkCreateComputePipelines:
                pipeline_info = self._parse_compute_pipeline(fc_data, chunk, shader_module_ids)
                if pipeline_info:
                    pipelines[pipeline_info.resource_id] = pipeline_info
        
        return draw_events, pipelines
    
    def _parse_marker_begin(self, data: bytes, chunk: ChunkInfo) -> Optional[str]:
        """解析 vkCmdBeginDebugUtilsLabelEXT，提取 marker 名称
        
        序列化格式:
        1. commandBuffer: ResourceId (8 bytes)
        2. Label.sType: uint32 (4 bytes) - VK_STRUCTURE_TYPE_DEBUG_UTILS_LABEL_EXT
        3. Label.pNext: 通常为 NULL
        4. Label.pLabelName: 字符串（int32 长度 + 字符数据）
        5. Label.color[4]: float[4] (16 bytes)
        """
        try:
            offset = chunk.data_offset
            chunk_end = offset + chunk.length
            
            # 跳过 commandBuffer ResourceId
            offset += 8
            
            if offset + 12 > chunk_end:
                return None
            
            # 跳过 sType (4) + pNext (通常 8)
            # 读取 pLabelName 字符串
            # 字符串格式: int32 len (-1 表示 NULL, 否则为长度)
            
            # 尝试找到字符串长度字段
            # 搜索范围：偏移 8-32 字节内
            for str_offset in range(8, min(40, chunk.length - 4)):
                pos = chunk.data_offset + str_offset
                strlen = struct.unpack_from('<i', data, pos)[0]
                
                # 合理的字符串长度: 1-256
                if 1 <= strlen <= 256 and pos + 4 + strlen <= chunk_end:
                    # 读取字符串
                    try:
                        label_bytes = data[pos + 4:pos + 4 + strlen]
                        label = label_bytes.decode('utf-8', errors='replace')
                        # 验证是否像是有意义的 marker 名称
                        if label and any(c.isalnum() for c in label):
                            return label
                    except:
                        continue
            
            return None
            
        except Exception as e:
            print(f"Warning: Failed to parse marker: {e}")
            return None
    
    def _parse_bind_pipeline(self, data: bytes, chunk: ChunkInfo) -> Tuple[int, int]:
        """解析 vkCmdBindPipeline，提取 bind point 和 pipeline ResourceId
        
        序列化格式:
        1. commandBuffer: ResourceId (8 bytes)
        2. pipelineBindPoint: VkPipelineBindPoint (4 bytes, enum)
        3. pipeline: ResourceId (8 bytes)
        
        Returns:
            (bind_point, pipeline_resource_id)
            bind_point: 0=Graphics, 1=Compute, 2=RayTracing
        """
        try:
            offset = chunk.data_offset
            
            if chunk.length < 20:
                return (-1, 0)
            
            # commandBuffer (8)
            # pipelineBindPoint (4)
            # pipeline (8)
            bind_point = struct.unpack_from('<I', data, offset + 8)[0]
            pipeline_id = struct.unpack_from('<Q', data, offset + 12)[0]
            
            return (bind_point, pipeline_id)
            
        except Exception as e:
            print(f"Warning: Failed to parse BindPipeline: {e}")
            return (-1, 0)
    
    def _get_draw_event_type(self, chunk_id: int) -> str:
        """根据 Chunk ID 返回 Draw 事件类型名称"""
        type_map = {
            VulkanChunk.vkCmdDraw: 'draw',
            VulkanChunk.vkCmdDrawIndirect: 'draw_indirect',
            VulkanChunk.vkCmdDrawIndexed: 'draw_indexed',
            VulkanChunk.vkCmdDrawIndexedIndirect: 'draw_indexed_indirect',
        }
        return type_map.get(chunk_id, 'draw')
    
    def _parse_graphics_pipeline(self, data: bytes, chunk: ChunkInfo, 
                                 known_shader_ids: Dict[int, int]) -> Optional[PipelineInfo]:
        """解析 vkCreateGraphicsPipelines，提取 Pipeline 和 Shader 关联
        
        使用启发式搜索：在 Pipeline chunk 中搜索已知的 ShaderModule ResourceIDs。
        
        Args:
            data: Frame capture 原始数据
            chunk: Pipeline chunk 信息
            known_shader_ids: 已知的 ShaderModule ID -> chunk_index 映射
        """
        try:
            offset = chunk.data_offset
            if chunk.length < 16:
                return None
            
            chunk_end = offset + chunk.length
            pipeline_id = struct.unpack_from('<Q', data, chunk_end - 8)[0]
            
            if pipeline_id == 0 or pipeline_id > (1 << 48):
                return None
            
            # 启发式搜索：在 chunk 数据中查找已知的 ShaderModule IDs
            shader_stages = self._search_shader_modules_in_chunk(
                data, chunk, known_shader_ids, is_graphics=True
            )
            
            return PipelineInfo(
                resource_id=pipeline_id,
                pipeline_type='graphics',
                shader_stages=shader_stages
            )
            
        except Exception:
            return None
    
    def _parse_compute_pipeline(self, data: bytes, chunk: ChunkInfo,
                                known_shader_ids: Dict[int, int]) -> Optional[PipelineInfo]:
        """解析 vkCreateComputePipelines，提取 Pipeline 和 Compute Shader 关联
        
        Args:
            data: Frame capture 原始数据
            chunk: Pipeline chunk 信息
            known_shader_ids: 已知的 ShaderModule ID -> chunk_index 映射
        """
        try:
            offset = chunk.data_offset
            if chunk.length < 16:
                return None
            
            chunk_end = offset + chunk.length
            pipeline_id = struct.unpack_from('<Q', data, chunk_end - 8)[0]
            
            if pipeline_id == 0 or pipeline_id > (1 << 48):
                return None
            
            # 启发式搜索 compute shader
            shader_stages = self._search_shader_modules_in_chunk(
                data, chunk, known_shader_ids, is_graphics=False
            )
            
            return PipelineInfo(
                resource_id=pipeline_id,
                pipeline_type='compute',
                shader_stages=shader_stages
            )
            
        except Exception:
            return None
    
    def _search_shader_modules_in_chunk(self, data: bytes, chunk: ChunkInfo,
                                        known_shader_ids: Dict[int, int],
                                        is_graphics: bool) -> Dict[str, int]:
        """在 Pipeline chunk 中搜索已知的 ShaderModule IDs
        
        这是一个启发式方法：由于 Vulkan 序列化格式复杂且包含 pNext 链，
        直接按偏移解析很容易出错。我们改为：
        1. 遍历 chunk 中所有可能的 8 字节对齐位置
        2. 检查该位置的 uint64 是否匹配已知的 ShaderModule ID
        3. 根据找到 ID 的顺序推断 Shader Stage
        
        Args:
            data: 原始数据
            chunk: chunk 信息  
            known_shader_ids: 已知的 ShaderModule IDs
            is_graphics: 是否为 Graphics Pipeline
            
        Returns:
            stage_name -> shader_module_id 映射
        """
        shader_stages: Dict[str, int] = {}
        found_modules: List[Tuple[int, int]] = []  # (offset, module_id)
        
        # 扫描 chunk 中所有 8 字节对齐位置
        start = chunk.data_offset
        end = start + chunk.length - 8
        
        for pos in range(start, end, 8):
            try:
                value = struct.unpack_from('<Q', data, pos)[0]
                if value in known_shader_ids:
                    found_modules.append((pos, value))
            except Exception:
                continue
        
        if not found_modules:
            return shader_stages
        
        # 去重（同一个 module 可能被多次引用，只取第一次）
        seen_modules = set()
        unique_modules = []
        for offset, mid in found_modules:
            if mid not in seen_modules:
                seen_modules.add(mid)
                unique_modules.append((offset, mid))
        
        if is_graphics:
            # Graphics Pipeline 通常按 VS, TCS, TES, GS, FS 顺序
            # 但大多数 Pipeline 只有 VS 和 FS
            if len(unique_modules) == 1:
                # 只有一个 shader，可能是 VS-only 或者解析不完整
                shader_stages['VS'] = unique_modules[0][1]
            elif len(unique_modules) == 2:
                # 最常见：VS + FS
                shader_stages['VS'] = unique_modules[0][1]
                shader_stages['FS'] = unique_modules[1][1]
            else:
                # 多个 stages，按顺序分配
                stage_order = ['VS', 'TCS', 'TES', 'GS', 'FS']
                for i, (_, mid) in enumerate(unique_modules):
                    if i < len(stage_order):
                        shader_stages[stage_order[i]] = mid
                    else:
                        shader_stages[f'STAGE{i}'] = mid
        else:
            # Compute Pipeline 只有一个 CS
            if unique_modules:
                shader_stages['CS'] = unique_modules[0][1]
        
        return shader_stages


# ============================================================================
# 便捷函数
# ============================================================================

def parse_rdc(filepath: str) -> RDCFileInfo:
    """解析 RDC 文件并返回基本信息"""
    with RDCParser(filepath) as parser:
        return parser.parse_header()


def extract_shaders(filepath: str) -> List[ShaderInfo]:
    """从 RDC 文件中提取所有 Shader"""
    with RDCParser(filepath) as parser:
        parser.parse_header()
        return parser.extract_vulkan_shaders()


def extract_textures(filepath: str) -> List[TextureInfo]:
    """从 RDC 文件中提取所有纹理元数据
    
    支持的 API:
    - Vulkan: 从 vkCreateImage chunks 提取
    - D3D11/D3D12: 暂不支持，返回空列表
    """
    with RDCParser(filepath) as parser:
        info = parser.parse_header()
        if info.is_vulkan:
            return parser.extract_vulkan_textures()
        else:
            # D3D11/D3D12 纹理提取尚未实现
            # TODO: 实现 D3D11 纹理解析
            return []


def extract_draw_events(filepath: str) -> Tuple[List[DrawEventContext], Dict[int, PipelineInfo]]:
    """从 RDC 文件中提取所有 Draw/Dispatch 事件及上下文
    
    支持的 API:
    - Vulkan: 完整支持
    - D3D11/D3D12: 暂不支持，返回空列表
    
    Returns:
        (draw_events, pipelines) 元组
    """
    with RDCParser(filepath) as parser:
        info = parser.parse_header()
        if info.is_vulkan:
            return parser.extract_draw_events()
        else:
            # D3D11/D3D12 尚未实现
            return ([], {})


def extract_resource_renames(filepath: str) -> Dict[int, str]:
    """从 RDC 文件中提取用户自定义的资源名称
    
    在 RenderDoc UI 中，用户可以通过右键菜单 "Set Custom Name" 为资源
    （纹理、缓冲区等）设置自定义名称。这些名称被保存在 RDC 文件的 
    ResourceRenames section 中。
    
    Args:
        filepath: RDC 文件路径
        
    Returns:
        Dict[int, str]: ResourceID (整数) -> 自定义名称 的映射
                       如果没有自定义名称或 section 不存在，返回空字典
    
    Example:
        >>> renames = extract_resource_renames("capture.rdc")
        >>> print(renames)
        {119808: 'MainRenderTarget', 119820: 'ShadowMap'}
    """
    with RDCParser(filepath) as parser:
        parser.parse_header()
        return parser.parse_resource_renames()


def print_rdc_info(filepath: str):
    """打印 RDC 文件信息"""
    info = parse_rdc(filepath)
    
    print(f"=" * 60)
    print(f"RDC File: {info.filepath}")
    print(f"=" * 60)
    print(f"File Size: {info.file_size / 1024 / 1024:.2f} MB")
    print(f"Version: {info.header.version_string}")
    print(f"Program: {info.header.prog_version}")
    print(f"Driver: {info.metadata.driver_name} ({info.metadata.driver_id.name})")
    print(f"Thumbnail: {info.thumbnail.width}x{info.thumbnail.height}")
    
    print(f"\nSections ({len(info.sections)}):")
    for i, section in enumerate(info.sections):
        comp_ratio = section.uncompressed_size / section.compressed_size if section.compressed_size > 0 else 1
        print(f"  [{i}] {section.name}")
        print(f"      Type: {section.section_type.name}")
        print(f"      Size: {section.compressed_size / 1024 / 1024:.2f} MB "
              f"(uncompressed: {section.uncompressed_size / 1024 / 1024:.2f} MB, "
              f"ratio: {comp_ratio:.1f}x)")
        print(f"      Compression: {section.compression_type}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python rdc_parser.py <rdc_file> [--extract-shaders]")
        sys.exit(1)
    
    rdc_path = sys.argv[1]
    
    if not os.path.exists(rdc_path):
        print(f"Error: File not found: {rdc_path}")
        sys.exit(1)
    
    try:
        print_rdc_info(rdc_path)
        
        if '--extract-shaders' in sys.argv:
            print(f"\n" + "=" * 60)
            print("Extracting Shaders...")
            print("=" * 60)
            
            shaders = extract_shaders(rdc_path)
            print(f"Found {len(shaders)} valid SPIR-V shaders")
            
            for i, shader in enumerate(shaders):
                print(f"  [{i}] Size: {shader.code_size} bytes, "
                      f"SPIR-V Version: {shader.spirv_version}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
