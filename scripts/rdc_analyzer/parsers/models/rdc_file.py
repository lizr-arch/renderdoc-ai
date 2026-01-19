"""
RDC 文件信息数据模型
====================

包含 RDC 文件整体信息的聚合数据类。

从 rdc_parser.py 提取。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .base import (
    FileHeader, Thumbnail, CaptureMetaData, TimeBase,
    SectionInfo, ChunkInfo, DrawEventContext, PipelineInfo
)
from .shader import ShaderInfo
from .texture import TextureInfo


@dataclass
class RDCFileInfo:
    """RDC 文件完整信息
    
    聚合所有从 RDC 文件中提取的信息。
    """
    # 基础信息
    file_path: str
    file_size: int
    header: FileHeader
    
    # 元数据
    thumbnail: Optional[Thumbnail] = None
    capture_meta: Optional[CaptureMetaData] = None
    time_base: Optional[TimeBase] = None
    
    # Sections 和 Chunks
    sections: List[SectionInfo] = field(default_factory=list)
    chunks: List[ChunkInfo] = field(default_factory=list)
    
    # 资源列表
    shaders: List[ShaderInfo] = field(default_factory=list)
    textures: List[TextureInfo] = field(default_factory=list)
    
    # 事件追踪
    draw_events: List[DrawEventContext] = field(default_factory=list)
    pipelines: Dict[int, PipelineInfo] = field(default_factory=dict)
    
    # 调试信息
    debug_markers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """检查文件是否有效"""
        return self.header.is_valid if self.header else False
    
    @property
    def driver_name(self) -> str:
        """获取驱动名称"""
        if self.capture_meta:
            return self.capture_meta.driver_name
        return "Unknown"
    
    @property
    def version_info(self) -> str:
        """获取版本信息"""
        if self.header:
            return f"RDC {self.header.version_string} ({self.header.prog_version})"
        return "Unknown"
    
    @property
    def shader_count(self) -> int:
        return len(self.shaders)
    
    @property
    def texture_count(self) -> int:
        return len(self.textures)
    
    @property
    def draw_call_count(self) -> int:
        return len(self.draw_events)
    
    @property
    def total_shader_memory(self) -> int:
        """计算所有 Shader 的总大小（字节）"""
        return sum(s.code_size for s in self.shaders)
    
    @property
    def total_texture_memory(self) -> int:
        """估算所有纹理的总显存占用（字节）"""
        return sum(t.estimated_memory_bytes for t in self.textures)
    
    def get_shader_by_stage(self, stage: str) -> List[ShaderInfo]:
        """按阶段获取 Shader 列表"""
        return [s for s in self.shaders if s.stage == stage]
    
    def get_shader_by_resource_id(self, resource_id: int) -> Optional[ShaderInfo]:
        """按 ResourceId 获取 Shader"""
        for s in self.shaders:
            if s.resource_id == resource_id:
                return s
        return None
    
    def get_texture_by_resource_id(self, resource_id: int) -> Optional[TextureInfo]:
        """按 ResourceId 获取纹理"""
        for t in self.textures:
            if t.resource_id == resource_id:
                return t
        return None
    
    def get_pipeline(self, resource_id: int) -> Optional[PipelineInfo]:
        """获取 Pipeline 信息"""
        return self.pipelines.get(resource_id)
    
    def get_draw_events_by_marker(self, marker_contains: str) -> List[DrawEventContext]:
        """按 Marker 路径过滤 Draw Events"""
        return [e for e in self.draw_events if marker_contains in e.marker_path]
    
    def summary(self) -> Dict[str, Any]:
        """生成摘要信息"""
        return {
            'file_path': self.file_path,
            'file_size_mb': round(self.file_size / (1024 * 1024), 2),
            'version': self.version_info,
            'driver': self.driver_name,
            'sections': len(self.sections),
            'chunks': len(self.chunks),
            'shaders': self.shader_count,
            'textures': self.texture_count,
            'draw_calls': self.draw_call_count,
            'shader_memory_mb': round(self.total_shader_memory / (1024 * 1024), 2),
            'texture_memory_mb': round(self.total_texture_memory / (1024 * 1024), 2),
            'warnings': len(self.warnings),
        }
    
    def __repr__(self) -> str:
        return (f"RDCFileInfo(path={self.file_path!r}, "
                f"shaders={self.shader_count}, "
                f"textures={self.texture_count}, "
                f"draw_calls={self.draw_call_count})")
