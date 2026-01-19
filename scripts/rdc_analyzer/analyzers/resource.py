"""
资源分析器
==========

分析资源使用情况:
- 纹理: 尺寸、格式、Mipmap、内存占用
- Buffer: 大小、类型、绑定频率
- Shader: 类型、绑定次数
"""

from typing import Any, Dict, List, Set
from .base import BaseAnalyzer
from ..core.types import TextureInfo, BufferInfo, ShaderInfo
from ..utils.format_utils import classify_format, is_power_of_two
from ..utils.memory_utils import estimate_texture_memory, estimate_buffer_memory


class ResourceAnalyzer(BaseAnalyzer):
    """资源分析器"""
    
    name = "resource"
    description = "Resource usage analyzer (textures, buffers, shaders)"
    dependencies = ["frame"]
    
    def analyze(self) -> None:
        """执行资源分析"""
        if self.is_api_mode():
            self._analyze_api_mode()
        else:
            self._analyze_binary_mode()
        
        # 更新帧摘要
        self._update_summary()
    
    def _analyze_api_mode(self) -> None:
        """API 模式分析"""
        controller = self.context.parsed.controller
        if not controller:
            return
        
        try:
            import renderdoc as rd
        except ImportError:
            return
        
        # 获取资源列表
        resources = controller.GetResources()
        
        textures = []
        buffers = []
        shaders = []
        
        for res in resources:
            res_type = res.type
            
            # 纹理资源
            if res_type in (rd.ResourceType.Texture1D, rd.ResourceType.Texture2D,
                           rd.ResourceType.Texture3D, rd.ResourceType.TextureCube):
                tex_info = self._parse_texture_api(controller, res)
                if tex_info:
                    textures.append(tex_info)
            
            # Buffer 资源
            elif res_type == rd.ResourceType.Buffer:
                buf_info = self._parse_buffer_api(controller, res)
                if buf_info:
                    buffers.append(buf_info)
            
            # Shader 资源
            elif res_type == rd.ResourceType.Shader:
                shader_info = self._parse_shader_api(res)
                if shader_info:
                    shaders.append(shader_info)
        
        self.context.textures = textures
        self.context.buffers = buffers
        self.context.shaders = shaders
    
    def _parse_texture_api(self, controller: Any, res: Any) -> TextureInfo:
        """解析纹理资源 (API 模式)"""
        try:
            import renderdoc as rd
            
            # 获取纹理描述
            tex_desc = controller.GetTexture(res.resourceId)
            if not tex_desc:
                return None
            
            fmt_str = str(tex_desc.format.Name())
            fmt_cat = classify_format(fmt_str)
            
            # 估算内存 (返回字节)
            memory_bytes = estimate_texture_memory(
                tex_desc.width,
                tex_desc.height,
                fmt_str,
                tex_desc.mips,
                tex_desc.arraysize,
                tex_desc.depth,
            )
            
            return TextureInfo(
                resource_id=str(res.resourceId),
                name=res.name or f"Texture_{res.resourceId}",
                width=tex_desc.width,
                height=tex_desc.height,
                depth=tex_desc.depth,
                mip_levels=tex_desc.mips,
                array_size=tex_desc.arraysize,
                format=fmt_str,
                format_category=fmt_cat,
                is_render_target=bool(tex_desc.creationFlags & rd.TextureCreationFlags.RTV),
                is_depth_stencil=fmt_cat == "depth",
                memory_size=memory_bytes,
            )
        except Exception:
            return None
    
    def _parse_buffer_api(self, controller: Any, res: Any) -> BufferInfo:
        """解析 Buffer 资源 (API 模式)"""
        try:
            import renderdoc as rd
            
            buf_desc = controller.GetBuffer(res.resourceId)
            if not buf_desc:
                return None
            
            # 确定 Buffer 类型
            usage = []
            if buf_desc.creationFlags & rd.BufferCategory.Vertex:
                usage.append("Vertex")
            if buf_desc.creationFlags & rd.BufferCategory.Index:
                usage.append("Index")
            if buf_desc.creationFlags & rd.BufferCategory.Constants:
                usage.append("Constant")
            if buf_desc.creationFlags & rd.BufferCategory.ReadWrite:
                usage.append("UAV")
            
            return BufferInfo(
                resource_id=str(res.resourceId),
                name=res.name or f"Buffer_{res.resourceId}",
                size=buf_desc.length,
                usage=usage,
                is_constant_buffer="Constant" in usage,
            )
        except Exception:
            return None
    
    def _parse_shader_api(self, res: Any) -> ShaderInfo:
        """解析 Shader 资源 (API 模式)"""
        try:
            return ShaderInfo(
                resource_id=str(res.resourceId),
                name=res.name or f"Shader_{res.resourceId}",
                type="Unknown",  # 需要解析 stage
            )
        except Exception:
            return None
    
    def _analyze_binary_mode(self) -> None:
        """二进制模式分析 - 从 parsed.textures/buffers 提取"""
        parsed = self.context.parsed
        
        textures = []
        buffers = []
        shaders = []
        
        # 从 parsed.textures 构建 TextureInfo
        for i, tex_dict in enumerate(parsed.textures):
            textures.append(TextureInfo(
                resource_id=tex_dict.get("resource_id", f"tex_{i}"),
                name=tex_dict.get("name", f"Texture_{i}"),
                width=tex_dict.get("width", 0),
                height=tex_dict.get("height", 0),
                format=tex_dict.get("format", ""),
            ))
        
        # 从 parsed.buffers 构建 BufferInfo
        for i, buf_dict in enumerate(parsed.buffers):
            buffers.append(BufferInfo(
                resource_id=buf_dict.get("resource_id", f"buf_{i}"),
                name=buf_dict.get("name", f"Buffer_{i}"),
                size=buf_dict.get("size", 0),
            ))
        
        # 从 parsed.shaders 构建 ShaderInfo
        for i, shader_dict in enumerate(parsed.shaders):
            shaders.append(ShaderInfo(
                resource_id=shader_dict.get("resource_id", f"shader_{i}"),
                name=shader_dict.get("name", f"Shader_{i}"),
                type=shader_dict.get("type", "Unknown"),
            ))
        
        self.context.textures = textures
        self.context.buffers = buffers
        self.context.shaders = shaders
    
    def _update_summary(self) -> None:
        """更新帧摘要中的资源统计"""
        summary = self.context.frame_summary
        
        summary.texture_count = len(self.context.textures)
        summary.buffer_count = len(self.context.buffers)
        
        # 计算内存 (memory_size 是字节, 转为总计)
        summary.total_texture_memory = sum(t.memory_size for t in self.context.textures)
        summary.total_buffer_memory = sum(b.size for b in self.context.buffers)