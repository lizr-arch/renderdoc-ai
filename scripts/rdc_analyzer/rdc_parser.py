#!/usr/bin/env python3
"""
RDC File Parser - 独立解析 RenderDoc 捕获文件

本模块为向后兼容薄包装层 (Thin Wrapper)。
实际解析逻辑已迁移至 parsers/ 子包。

推荐新代码直接使用:
    from parsers import (
        SectionParser, ChunkParser, ShaderExtractor,
        TextureExtractor, DrawEventParser, parse_rdc_file
    )

Author: RenderDoc Mali Analyzer Project
Version: 2.0.0 (Refactored)
"""

import warnings
from typing import List, Optional, Dict, Any

# ============================================================================
# 从 parsers 包导入所有必需类型（向后兼容）
# ============================================================================

from parsers import (
    # 常量
    RDC_MAGIC_BYTES,
    RDC_VERSION_1_0,
    RDC_VERSION_1_1,
    RDC_VERSION_1_2,
    FIRST_DRIVER_CHUNK,
    CHUNK_ALIGNMENT,
    CHUNK_64BIT_SIZE,
    CHUNK_INDEX_MASK,
    CHUNK_CALLSTACK,
    CHUNK_THREAD_ID,
    CHUNK_DURATION,
    CHUNK_TIMESTAMP,
    SPIRV_MAGIC,
    SPIRV_OP_NAME,
    SPIRV_OP_ENTRY_POINT,
    SPIRV_EXEC_MODEL_NAMES,
    # 枚举
    RDCDriver,
    SectionType,
    SectionFlags,
    VulkanChunk,
    VK_FORMAT_NAMES,
    # 数据模型
    FileHeader,
    Thumbnail,
    CaptureMetaData,
    TimeBase,
    SectionInfo,
    ChunkInfo,
    DrawEventContext,
    PipelineInfo,
    ShaderResource,
    SPIRVEntryPoint,
    ShaderInfo,
    TextureInfo,
    RDCFileInfo,
    # IO 工具
    BinaryReader,
    read_u8_from_bytes,
    read_u16_from_bytes,
    read_u32_from_bytes,
    read_u64_from_bytes,
    read_i32_from_bytes,
    read_f32_from_bytes,
    read_f64_from_bytes,
    read_string_from_bytes,
    align_offset,
    # 解析器
    SectionParser,
    parse_rdc_file,
    ChunkParser,
    parse_frame_chunks,
    ShaderExtractor,
    extract_vulkan_shaders,
    TextureExtractor,
    extract_vulkan_textures,
    DrawEventParser,
    extract_draw_events,
    MARKER_BEGIN_CHUNK_IDS,
    MARKER_END_CHUNK_IDS,
    DRAW_CHUNK_IDS,
    DISPATCH_CHUNK_IDS,
)

# ============================================================================
# 废弃常量（保留以兼容旧代码）
# ============================================================================

RDC_MAGIC = 0x434F4452  # 'RDOC' in little-endian

# ============================================================================
# RDCParser 类（向后兼容薄包装）
# ============================================================================

class RDCParser:
    """
    RDC 文件解析器（向后兼容薄包装）
    
    ⚠️ DEPRECATED: 建议新代码使用 parsers 包中的独立解析器：
        - SectionParser: 解析文件头和 Section
        - ChunkParser: 解析 Frame Chunks
        - ShaderExtractor: 提取 SPIR-V Shader
        - TextureExtractor: 提取纹理元数据
        - DrawEventParser: 解析 Draw 事件
    
    使用示例（新 API）:
        from parsers import parse_rdc_file, extract_vulkan_shaders
        
        rdc_info = parse_rdc_file("capture.rdc")
        shaders = extract_vulkan_shaders("capture.rdc")
    
    使用示例（旧 API，仍可用）:
        with RDCParser("capture.rdc") as parser:
            info = parser.parse_header()
            shaders = parser.extract_vulkan_shaders()
    """
    
    def __init__(self, filepath: str):
        """初始化解析器"""
        self.filepath = filepath
        self._section_parser: Optional[SectionParser] = None
        self._chunk_parser: Optional[ChunkParser] = None
        self._shader_extractor: Optional[ShaderExtractor] = None
        self._texture_extractor: Optional[TextureExtractor] = None
        self._draw_event_parser: Optional[DrawEventParser] = None
        self._rdc_info: Optional[RDCFileInfo] = None
        self._chunks: Optional[List[ChunkInfo]] = None
        
        # 发出废弃警告
        warnings.warn(
            "RDCParser 已废弃，建议使用 parsers 包中的独立解析器。"
            "例如: from parsers import parse_rdc_file, extract_vulkan_shaders",
            DeprecationWarning,
            stacklevel=2
        )
    
    def __enter__(self):
        """上下文管理器入口"""
        self._section_parser = SectionParser(self.filepath)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        if self._section_parser:
            self._section_parser.close()
            self._section_parser = None
    
    # ========================================================================
    # 文件头解析（委托给 SectionParser）
    # ========================================================================
    
    def parse_header(self) -> RDCFileInfo:
        """
        解析 RDC 文件头和元数据
        
        Returns:
            RDCFileInfo: 文件信息对象
        """
        if self._section_parser is None:
            raise RuntimeError("请在 with 语句中使用 RDCParser")
        
        self._rdc_info = self._section_parser.parse()
        return self._rdc_info
    
    def read_section_data(self, section: SectionInfo) -> bytes:
        """
        读取并解压 Section 数据
        
        Args:
            section: Section 信息对象
            
        Returns:
            bytes: 解压后的数据
        """
        if self._section_parser is None:
            raise RuntimeError("请在 with 语句中使用 RDCParser")
        
        return self._section_parser.read_section_data(section)
    
    # ========================================================================
    # Chunk 解析（委托给 ChunkParser）
    # ========================================================================
    
    def parse_frame_chunks(self) -> List[ChunkInfo]:
        """
        解析 FrameCapture 中的所有 Chunks
        
        Returns:
            List[ChunkInfo]: Chunk 列表
        """
        if self._rdc_info is None:
            self.parse_header()
        
        frame_section = self._rdc_info.frame_capture_section
        if frame_section is None:
            return []
        
        section_data = self.read_section_data(frame_section)
        self._chunk_parser = ChunkParser(section_data)
        self._chunks = self._chunk_parser.parse_all()
        return self._chunks
    
    # ========================================================================
    # Shader 提取（委托给 ShaderExtractor）
    # ========================================================================
    
    def extract_vulkan_shaders(self) -> List[ShaderInfo]:
        """
        提取所有 Vulkan SPIR-V Shader
        
        Returns:
            List[ShaderInfo]: Shader 信息列表
        """
        if self._chunks is None:
            self.parse_frame_chunks()
        
        self._shader_extractor = ShaderExtractor(self._chunks)
        return self._shader_extractor.extract_all()
    
    # ========================================================================
    # 纹理提取（委托给 TextureExtractor）
    # ========================================================================
    
    def extract_vulkan_textures(self) -> List[TextureInfo]:
        """
        提取所有 Vulkan 纹理元数据
        
        Returns:
            List[TextureInfo]: 纹理信息列表
        """
        if self._chunks is None:
            self.parse_frame_chunks()
        
        self._texture_extractor = TextureExtractor(self._chunks)
        return self._texture_extractor.extract_all()
    
    # ========================================================================
    # Draw 事件解析（委托给 DrawEventParser）
    # ========================================================================
    
    def extract_draw_events(self) -> List[DrawEventContext]:
        """
        提取所有 Draw/Dispatch 事件及其上下文
        
        Returns:
            List[DrawEventContext]: Draw 事件列表
        """
        if self._chunks is None:
            self.parse_frame_chunks()
        
        self._draw_event_parser = DrawEventParser(self._chunks)
        return self._draw_event_parser.extract_all()
    
    # ========================================================================
    # 便捷方法
    # ========================================================================
    
    @property
    def file_size(self) -> int:
        """获取文件大小"""
        import os
        return os.path.getsize(self.filepath)
    
    @property
    def rdc_info(self) -> Optional[RDCFileInfo]:
        """获取已解析的 RDC 信息"""
        return self._rdc_info
    
    @property
    def chunks(self) -> Optional[List[ChunkInfo]]:
        """获取已解析的 Chunks"""
        return self._chunks


# ============================================================================
# 便捷函数（向后兼容）
# ============================================================================

def parse_rdc(filepath: str) -> RDCFileInfo:
    """
    解析 RDC 文件（便捷函数）
    
    ⚠️ DEPRECATED: 建议使用 parsers.parse_rdc_file()
    
    Args:
        filepath: RDC 文件路径
        
    Returns:
        RDCFileInfo: 文件信息
    """
    warnings.warn(
        "parse_rdc() 已废弃，请使用 parsers.parse_rdc_file()",
        DeprecationWarning,
        stacklevel=2
    )
    return parse_rdc_file(filepath)


def extract_shaders(filepath: str) -> List[ShaderInfo]:
    """
    提取 RDC 文件中的所有 Shader（便捷函数）
    
    ⚠️ DEPRECATED: 建议使用 parsers.extract_vulkan_shaders()
    
    Args:
        filepath: RDC 文件路径
        
    Returns:
        List[ShaderInfo]: Shader 列表
    """
    warnings.warn(
        "extract_shaders() 已废弃，请使用 parsers.extract_vulkan_shaders()",
        DeprecationWarning,
        stacklevel=2
    )
    return extract_vulkan_shaders(filepath)


def extract_textures(filepath: str) -> List[TextureInfo]:
    """
    提取 RDC 文件中的所有纹理（便捷函数）
    
    ⚠️ DEPRECATED: 建议使用 parsers.extract_vulkan_textures()
    
    Args:
        filepath: RDC 文件路径
        
    Returns:
        List[TextureInfo]: 纹理列表
    """
    warnings.warn(
        "extract_textures() 已废弃，请使用 parsers.extract_vulkan_textures()",
        DeprecationWarning,
        stacklevel=2
    )
    return extract_vulkan_textures(filepath)


# ============================================================================
# __all__ 导出（保持 API 兼容）
# ============================================================================

__all__ = [
    # 常量
    'RDC_MAGIC',
    'RDC_MAGIC_BYTES',
    'RDC_VERSION_1_0',
    'RDC_VERSION_1_1',
    'RDC_VERSION_1_2',
    'FIRST_DRIVER_CHUNK',
    'CHUNK_ALIGNMENT',
    'CHUNK_64BIT_SIZE',
    'SPIRV_MAGIC',
    # 枚举
    'RDCDriver',
    'SectionType',
    'SectionFlags',
    'VulkanChunk',
    'VK_FORMAT_NAMES',
    # 数据模型
    'FileHeader',
    'Thumbnail',
    'CaptureMetaData',
    'TimeBase',
    'SectionInfo',
    'ChunkInfo',
    'DrawEventContext',
    'PipelineInfo',
    'ShaderResource',
    'SPIRVEntryPoint',
    'ShaderInfo',
    'TextureInfo',
    'RDCFileInfo',
    # 解析器类
    'RDCParser',
    # 便捷函数
    'parse_rdc',
    'extract_shaders',
    'extract_textures',
    # 新 API（推荐）
    'parse_rdc_file',
    'parse_frame_chunks',
    'extract_vulkan_shaders',
    'extract_vulkan_textures',
    'extract_draw_events',
]


# ============================================================================
# 主函数（测试/演示）
# ============================================================================

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python rdc_parser.py <rdc_file>")
        print("\n推荐使用新 API:")
        print("  from parsers import parse_rdc_file, extract_vulkan_shaders")
        print("  info = parse_rdc_file('capture.rdc')")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    print(f"解析 RDC 文件: {filepath}")
    print("=" * 60)
    
    # 使用新 API 演示
    print("\n[使用新 API - parsers 包]")
    
    info = parse_rdc_file(filepath)
    print(f"  Driver: {info.driver_name}")
    print(f"  Version: {info.header.prog_version}")
    print(f"  Sections: {len(info.sections)}")
    
    # 提取 chunks
    frame_section = info.frame_capture_section
    if frame_section:
        parser = SectionParser(filepath)
        try:
            parser.parse()
            section_data = parser.read_section_data(frame_section)
            chunks = parse_frame_chunks(section_data)
            print(f"  Chunks: {len(chunks)}")
            
            # 提取各类数据
            shaders = extract_vulkan_shaders(filepath)
            print(f"  Shaders: {len(shaders)}")
            
            textures = extract_vulkan_textures(filepath)
            print(f"  Textures: {len(textures)}")
            
            events = extract_draw_events(filepath)
            print(f"  Draw Events: {len(events)}")
        finally:
            parser.close()
    
    print("\n✅ 解析完成")
