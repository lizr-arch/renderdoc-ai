"""
RDC 基础数据模型
================

包含 RDC 文件头和 Section/Chunk 信息的数据类。

从 rdc_parser.py 提取。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict

from ..constants import (
    RDC_MAGIC_BYTES, CHUNK_64BIT_SIZE, FIRST_DRIVER_CHUNK
)
from ..enums import (
    RDCDriver, SectionType, SectionFlags, VulkanChunk
)


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
            'draw_indirect_count': 'DrawIndirectCount',
            'draw_indexed_indirect_count': 'DrawIndexedIndirectCount',
            'draw_mesh_tasks': 'DrawMeshTasks',
            'draw_mesh_tasks_indirect': 'DrawMeshTasksIndirect',
            'draw_mesh_tasks_indirect_count': 'DrawMeshTasksIndirectCount',
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
