"""
Texture 数据模型
================

包含纹理资源信息的数据类。

从 rdc_parser.py 提取。
"""

from dataclasses import dataclass
from typing import Optional, Union

from ..enums import VK_FORMAT_NAMES


# 深度/模板格式的值（从 Vulkan 规范）
_DEPTH_FORMATS = {
    124,  # VK_FORMAT_D16_UNORM
    125,  # VK_FORMAT_X8_D24_UNORM_PACK32
    126,  # VK_FORMAT_D32_SFLOAT
    127,  # VK_FORMAT_S8_UINT
    128,  # VK_FORMAT_D16_UNORM_S8_UINT
    129,  # VK_FORMAT_D24_UNORM_S8_UINT
    130,  # VK_FORMAT_D32_SFLOAT_S8_UINT
}


@dataclass
class TextureInfo:
    """提取的纹理信息"""
    resource_id: int
    width: int
    height: int
    depth: int
    mip_levels: int
    array_size: int
    format: int  # VkFormat 整数值
    samples: int
    chunk_offset: int  # 在 FrameCapture 中的偏移
    
    # 可选字段
    name: Optional[str] = None  # 调试名称
    usage: Optional[str] = None  # 用途（如 color, depth, staging 等）
    
    @property
    def format_name(self) -> str:
        """获取格式名称"""
        return VK_FORMAT_NAMES.get(self.format, f"VK_FORMAT_{self.format}")
    
    @property
    def dimensions(self) -> str:
        """获取维度描述"""
        if self.depth > 1:
            return f"{self.width}x{self.height}x{self.depth}"
        elif self.array_size > 1:
            return f"{self.width}x{self.height}[{self.array_size}]"
        return f"{self.width}x{self.height}"
    
    @property
    def is_render_target(self) -> bool:
        """判断是否是渲染目标（基于尺寸和格式推断）"""
        # 通常渲染目标是 2 的幂次方尺寸
        def is_power_of_two(n):
            return n > 0 and (n & (n - 1)) == 0
        
        return (is_power_of_two(self.width) and 
                is_power_of_two(self.height) and
                self.samples >= 1)
    
    @property
    def is_depth_stencil(self) -> bool:
        """判断是否是深度/模板纹理"""
        return self.format in _DEPTH_FORMATS
    
    @property
    def estimated_memory_bytes(self) -> int:
        """估算显存占用（字节）"""
        # 简化估算：假设每像素 4 字节，考虑 mip levels
        bytes_per_pixel = 4  # 粗略估计
        
        # 根据格式调整
        format_name = self.format_name.lower()
        if 'r8' in format_name:
            bytes_per_pixel = 1
        elif 'r16' in format_name or 'rg8' in format_name:
            bytes_per_pixel = 2
        elif 'rgba8' in format_name or 'bgra8' in format_name:
            bytes_per_pixel = 4
        elif 'rgba16' in format_name:
            bytes_per_pixel = 8
        elif 'rgba32' in format_name:
            bytes_per_pixel = 16
        elif 'bc1' in format_name or 'bc4' in format_name:
            bytes_per_pixel = 0.5  # 压缩格式
        elif 'bc2' in format_name or 'bc3' in format_name or 'bc5' in format_name:
            bytes_per_pixel = 1
        elif 'bc6' in format_name or 'bc7' in format_name:
            bytes_per_pixel = 1
        
        # 基础尺寸
        base_size = self.width * self.height * self.depth * bytes_per_pixel
        
        # Mip levels (大约增加 1/3)
        if self.mip_levels > 1:
            base_size = int(base_size * 1.33)
        
        # Array layers
        base_size *= self.array_size
        
        # MSAA samples
        base_size *= max(1, self.samples)
        
        return int(base_size)
    
    @property
    def memory_size_human(self) -> str:
        """获取人类可读的内存大小"""
        size = self.estimated_memory_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        if self.name:
            return self.name
        return f"Texture_{self.resource_id:x}"
    
    @property
    def type_description(self) -> str:
        """获取纹理类型描述"""
        if self.depth > 1:
            return "3D"
        elif self.array_size > 6:
            return f"2DArray[{self.array_size}]"
        elif self.array_size == 6:
            return "Cubemap"
        elif self.samples > 1:
            return f"2D MSAA {self.samples}x"
        return "2D"
