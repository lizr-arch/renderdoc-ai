# -*- coding: utf-8 -*-
"""
Resource Inspector - 资源数据检查器
===================================
移除初始编码声明
"""

import struct
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum


class ResourceType(Enum):
    """资源类型"""
    BUFFER = "buffer"
    TEXTURE_1D = "texture_1d"
    TEXTURE_2D = "texture_2d"
    TEXTURE_3D = "texture_3d"
    TEXTURE_CUBE = "texture_cube"
    UNKNOWN = "unknown"


@dataclass
class ResourceInfo:
    """资源基本信息"""
    resource_id: int
    name: str
    resource_type: ResourceType
    size: int  # 字节大小
    format: str = ""  # 格式字符串 (如 R32G32B32A32_FLOAT)
    width: int = 0
    height: int = 0
    depth: int = 0
    mip_levels: int = 1
    array_size: int = 1


@dataclass 
class BufferData:
    """Buffer 数据结果"""
    resource_id: int
    event_id: int
    size: int
    data: bytes
    offset: int = 0
    

@dataclass
class TextureData:
    """Texture 数据结果"""
    resource_id: int
    event_id: int
    width: int
    height: int
    depth: int
    format: str
    mip_level: int
    array_index: int
    data: bytes


class ResourceInspector:
    """
    资源检查器
    
    使用 RenderDoc ReplayController API 检查资源数据。
    
    用法:
        inspector = ResourceInspector(controller)
        
        # 获取 Buffer 数据
        buffer_data = inspector.get_buffer_data(resource_id=3002, event_id=120)
        
        # 获取 Texture 数据
        texture_data = inspector.get_texture_data(resource_id=5001, event_id=200)
    """
    
    def __init__(self, controller=None):
        """
        初始化资源检查器
        
        Args:
            controller: RenderDoc ReplayController 实例
        """
        self.controller = controller
        self._resource_cache: Dict[int, ResourceInfo] = {}
        
    def set_controller(self, controller):
        """设置 ReplayController"""
        self.controller = controller
        
    def get_resource_info(self, resource_id: int) -> Optional[ResourceInfo]:
        """
        获取资源基本信息
        
        Args:
            resource_id: 资源 ID
            
        Returns:
            ResourceInfo 或 None
        """
        if resource_id in self._resource_cache:
            return self._resource_cache[resource_id]
            
        if not self.controller:
            return None
            
        try:
            # 尝试获取资源描述
            resources = self.controller.GetResources()
            for res in resources:
                if res.resourceId == resource_id:
                    info = self._parse_resource_descriptor(res)
                    self._resource_cache[resource_id] = info
                    return info
        except Exception as e:
            print(f"[ResourceInspector] Error getting resource info: {e}")
            
        return None
        
    def _parse_resource_descriptor(self, res) -> ResourceInfo:
        """解析资源描述符"""
        import renderdoc as rd
        
        res_type = ResourceType.UNKNOWN
        width = height = depth = 0
        format_str = ""
        size = 0
        mip_levels = 1
        array_size = 1
        
        # 判断资源类型
        if hasattr(res, 'type'):
            if res.type == rd.ResourceType.Buffer:
                res_type = ResourceType.BUFFER
                if hasattr(res, 'length'):
                    size = res.length
            elif res.type == rd.ResourceType.Texture:
                # 进一步判断纹理维度
                if hasattr(res, 'dimension'):
                    if res.dimension == 1:
                        res_type = ResourceType.TEXTURE_1D
                    elif res.dimension == 2:
                        res_type = ResourceType.TEXTURE_2D
                    elif res.dimension == 3:
                        res_type = ResourceType.TEXTURE_3D
                else:
                    res_type = ResourceType.TEXTURE_2D
                    
                if hasattr(res, 'width'):
                    width = res.width
                if hasattr(res, 'height'):
                    height = res.height
                if hasattr(res, 'depth'):
                    depth = res.depth
                if hasattr(res, 'format'):
                    format_str = str(res.format)
                if hasattr(res, 'mips'):
                    mip_levels = res.mips
                if hasattr(res, 'arraysize'):
                    array_size = res.arraysize
                    
                size = width * height * max(depth, 1) * self._get_format_byte_size(format_str)
                
        name = getattr(res, 'name', f"Resource_{res.resourceId}")
        
        return ResourceInfo(
            resource_id=res.resourceId,
            name=name,
            resource_type=res_type,
            size=size,
            format=format_str,
            width=width,
            height=height,
            depth=depth,
            mip_levels=mip_levels,
            array_size=array_size
        )
        
    def _get_format_byte_size(self, format_str: str) -> int:
        """根据格式字符串获取每像素字节数"""
        format_sizes = {
            'R8': 1, 'R8G8': 2, 'R8G8B8A8': 4,
            'R16': 2, 'R16G16': 4, 'R16G16B16A16': 8,
            'R32': 4, 'R32G32': 8, 'R32G32B32': 12, 'R32G32B32A32': 16,
            'R11G11B10': 4,
            'R10G10B10A2': 4,
            'D16': 2, 'D24': 3, 'D32': 4, 'D24S8': 4, 'D32S8': 5,
            'BC1': 0.5, 'BC2': 1, 'BC3': 1, 'BC4': 0.5, 'BC5': 1, 'BC6': 1, 'BC7': 1,
        }
        
        for key, size in format_sizes.items():
            if key in format_str.upper():
                return int(size) if size >= 1 else 1
        return 4  # 默认 4 字节
        
    def get_buffer_data(
        self, 
        resource_id: int, 
        event_id: int,
        offset: int = 0,
        length: int = 0
    ) -> Optional[BufferData]:
        """
        获取 Buffer 数据
        
        Args:
            resource_id: Buffer 资源 ID
            event_id: 事件 ID (时间点)
            offset: 读取偏移量
            length: 读取长度 (0 表示全部)
            
        Returns:
            BufferData 或 None
        """
        if not self.controller:
            print("[ResourceInspector] No controller set")
            return None
            
        try:
            import renderdoc as rd
            
            # 跳转到指定事件
            self.controller.SetFrameEvent(event_id, True)
            
            # 创建资源 ID 对象
            res_id = rd.ResourceId()
            res_id.id = resource_id
            
            # 获取 Buffer 数据
            data = self.controller.GetBufferData(res_id, offset, length)
            
            if data is None or len(data) == 0:
                print(f"[ResourceInspector] No data returned for buffer {resource_id}")
                return None
                
            return BufferData(
                resource_id=resource_id,
                event_id=event_id,
                size=len(data),
                data=bytes(data),
                offset=offset
            )
            
        except Exception as e:
            print(f"[ResourceInspector] Error reading buffer {resource_id}: {e}")
            return None
            
    def get_texture_data(
        self,
        resource_id: int,
        event_id: int,
        mip_level: int = 0,
        array_index: int = 0
    ) -> Optional[TextureData]:
        """
        获取 Texture 数据
        
        Args:
            resource_id: Texture 资源 ID
            event_id: 事件 ID
            mip_level: Mip 级别
            array_index: 数组索引
            
        Returns:
            TextureData 或 None
        """
        if not self.controller:
            print("[ResourceInspector] No controller set")
            return None
            
        try:
            import renderdoc as rd
            
            # 跳转到指定事件
            self.controller.SetFrameEvent(event_id, True)
            
            # 创建资源 ID 对象
            res_id = rd.ResourceId()
            res_id.id = resource_id
            
            # 获取纹理数据
            # GetTextureData(resourceId, subresource, ...)
            sub = rd.Subresource(mip_level, array_index, 0)
            data = self.controller.GetTextureData(res_id, sub)
            
            if data is None or len(data) == 0:
                print(f"[ResourceInspector] No data returned for texture {resource_id}")
                return None
                
            # 获取纹理信息
            info = self.get_resource_info(resource_id)
            width = info.width if info else 0
            height = info.height if info else 0
            depth = info.depth if info else 1
            format_str = info.format if info else ""
            
            return TextureData(
                resource_id=resource_id,
                event_id=event_id,
                width=width,
                height=height,
                depth=depth,
                format=format_str,
                mip_level=mip_level,
                array_index=array_index,
                data=bytes(data)
            )
            
        except Exception as e:
            print(f"[ResourceInspector] Error reading texture {resource_id}: {e}")
            return None
            
    def list_resources(self, resource_type: Optional[ResourceType] = None) -> List[ResourceInfo]:
        """
        列出所有资源
        
        Args:
            resource_type: 可选，筛选特定类型
            
        Returns:
            ResourceInfo 列表
        """
        if not self.controller:
            return []
            
        try:
            resources = self.controller.GetResources()
            result = []
            
            for res in resources:
                info = self._parse_resource_descriptor(res)
                if resource_type is None or info.resource_type == resource_type:
                    result.append(info)
                    
            return result
            
        except Exception as e:
            print(f"[ResourceInspector] Error listing resources: {e}")
            return []


class BufferFormatParser:
    """
    Buffer 格式解析器
    
    将原始字节数据解析为结构化格式（顶点、索引、常量等）
    """
    
    # 常见格式到 struct 格式字符的映射
    FORMAT_MAP = {
        'R32_FLOAT': 'f',
        'R32G32_FLOAT': '2f',
        'R32G32B32_FLOAT': '3f',
        'R32G32B32A32_FLOAT': '4f',
        'R32_UINT': 'I',
        'R32G32_UINT': '2I',
        'R32G32B32_UINT': '3I',
        'R32G32B32A32_UINT': '4I',
        'R32_SINT': 'i',
        'R16_UINT': 'H',
        'R16G16_UINT': '2H',
        'R16G16B16A16_UINT': '4H',
        'R16_SINT': 'h',
        'R16_FLOAT': 'e',  # Half float
        'R16G16_FLOAT': '2e',
        'R16G16B16A16_FLOAT': '4e',
        'R8_UINT': 'B',
        'R8G8_UINT': '2B',
        'R8G8B8A8_UINT': '4B',
        'R8_UNORM': 'B',  # 需要后处理 /255
        'R8G8B8A8_UNORM': '4B',
    }
    
    def __init__(self):
        self.endian = '<'  # 小端序
        
    def parse_as_floats(self, data: bytes, components: int = 4) -> List[Tuple]:
        """
        将数据解析为浮点数元组列表
        
        Args:
            data: 原始字节
            components: 每个元素的分量数 (1-4)
            
        Returns:
            元组列表，每个元组包含 components 个浮点数
        """
        fmt = f'{self.endian}{components}f'
        stride = components * 4
        result = []
        
        for i in range(0, len(data) - stride + 1, stride):
            values = struct.unpack(fmt, data[i:i+stride])
            result.append(values)
            
        return result
        
    def parse_as_indices(self, data: bytes, index_format: str = 'R32_UINT') -> List[int]:
        """
        将数据解析为索引列表
        
        Args:
            data: 原始字节
            index_format: 索引格式 (R16_UINT 或 R32_UINT)
            
        Returns:
            索引值列表
        """
        if '16' in index_format:
            fmt = f'{self.endian}H'
            stride = 2
        else:
            fmt = f'{self.endian}I'
            stride = 4
            
        result = []
        for i in range(0, len(data) - stride + 1, stride):
            value = struct.unpack(fmt, data[i:i+stride])[0]
            result.append(value)
            
        return result
        
    def parse_vertex_buffer(
        self,
        data: bytes,
        layout: List[Dict[str, Any]],
        vertex_count: int = 0
    ) -> List[Dict[str, Any]]:
        """
        根据顶点布局解析顶点缓冲区
        
        Args:
            data: 原始字节
            layout: 顶点布局描述
                    [{'name': 'POSITION', 'format': 'R32G32B32_FLOAT', 'offset': 0},
                     {'name': 'NORMAL', 'format': 'R32G32B32_FLOAT', 'offset': 12},
                     {'name': 'TEXCOORD', 'format': 'R32G32_FLOAT', 'offset': 24}]
            vertex_count: 顶点数量 (0 表示自动计算)
            
        Returns:
            顶点数据字典列表
        """
        if not layout:
            return []
            
        # 计算 stride
        stride = 0
        for attr in layout:
            fmt = self.FORMAT_MAP.get(attr['format'], '4f')
            attr_size = struct.calcsize(f'{self.endian}{fmt}')
            stride = max(stride, attr['offset'] + attr_size)
            
        if stride == 0:
            return []
            
        # 计算顶点数
        if vertex_count == 0:
            vertex_count = len(data) // stride
            
        result = []
        for v in range(min(vertex_count, len(data) // stride)):
            vertex = {}
            base = v * stride
            
            for attr in layout:
                fmt = self.FORMAT_MAP.get(attr['format'], '4f')
                offset = attr['offset']
                
                try:
                    size = struct.calcsize(f'{self.endian}{fmt}')
                    values = struct.unpack(
                        f'{self.endian}{fmt}', 
                        data[base + offset:base + offset + size]
                    )
                    
                    # 单值情况
                    if len(values) == 1:
                        vertex[attr['name']] = values[0]
                    else:
                        vertex[attr['name']] = values
                        
                except struct.error:
                    vertex[attr['name']] = None
                    
            result.append(vertex)
            
        return result
        
    def parse_constant_buffer(
        self,
        data: bytes,
        layout: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        解析常量缓冲区
        
        Args:
            data: 原始字节
            layout: 常量布局描述
                    [{'name': 'WorldMatrix', 'type': 'float4x4', 'offset': 0},
                     {'name': 'ViewMatrix', 'type': 'float4x4', 'offset': 64}]
                     
        Returns:
            常量字典
        """
        result = {}
        
        type_formats = {
            'float': ('f', 4),
            'float2': ('2f', 8),
            'float3': ('3f', 12),
            'float4': ('4f', 16),
            'float4x4': ('16f', 64),
            'float3x3': ('9f', 36),
            'int': ('i', 4),
            'int2': ('2i', 8),
            'int3': ('3i', 12),
            'int4': ('4i', 16),
            'uint': ('I', 4),
            'uint2': ('2I', 8),
            'uint3': ('3I', 12),
            'uint4': ('4I', 16),
        }
        
        for const in layout:
            name = const['name']
            type_str = const.get('type', 'float4')
            offset = const.get('offset', 0)
            
            if type_str in type_formats:
                fmt, size = type_formats[type_str]
                try:
                    values = struct.unpack(
                        f'{self.endian}{fmt}',
                        data[offset:offset + size]
                    )
                    
                    # 矩阵类型转为嵌套列表
                    if '4x4' in type_str:
                        result[name] = [values[i:i+4] for i in range(0, 16, 4)]
                    elif '3x3' in type_str:
                        result[name] = [values[i:i+3] for i in range(0, 9, 3)]
                    elif len(values) == 1:
                        result[name] = values[0]
                    else:
                        result[name] = values
                        
                except struct.error:
                    result[name] = None
                    
        return result
        
    def hex_dump(self, data: bytes, bytes_per_line: int = 16, max_lines: int = 32) -> str:
        """
        生成十六进制转储
        
        Args:
            data: 原始字节
            bytes_per_line: 每行字节数
            max_lines: 最大行数
            
        Returns:
            格式化的十六进制字符串
        """
        lines = []
        max_bytes = min(len(data), bytes_per_line * max_lines)
        
        for offset in range(0, max_bytes, bytes_per_line):
            chunk = data[offset:offset + bytes_per_line]
            
            # 地址
            addr = f'{offset:08X}'
            
            # 十六进制部分
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            hex_part = hex_part.ljust(bytes_per_line * 3 - 1)
            
            # ASCII 部分
            ascii_part = ''.join(
                chr(b) if 32 <= b < 127 else '.'
                for b in chunk
            )
            
            lines.append(f'{addr}  {hex_part}  |{ascii_part}|')
            
        if len(data) > max_bytes:
            lines.append(f'... ({len(data) - max_bytes} more bytes)')
            
        return '\n'.join(lines)


def format_buffer_preview(data: bytes, max_floats: int = 16) -> str:
    """
    格式化 Buffer 数据预览
    
    Args:
        data: 原始字节
        max_floats: 最多显示的浮点数数量
        
    Returns:
        格式化字符串
    """
    parser = BufferFormatParser()
    
    lines = []
    lines.append(f"Buffer Size: {len(data)} bytes")
    lines.append("")
    
    # 作为 float4 解析
    floats = parser.parse_as_floats(data, 4)
    lines.append(f"As float4 ({len(floats)} vectors):")
    for i, vec in enumerate(floats[:max_floats//4]):
        lines.append(f"  [{i:4d}] ({vec[0]:12.6f}, {vec[1]:12.6f}, {vec[2]:12.6f}, {vec[3]:12.6f})")
    if len(floats) > max_floats//4:
        lines.append(f"  ... ({len(floats) - max_floats//4} more)")
    
    lines.append("")
    lines.append("Hex Dump:")
    lines.append(parser.hex_dump(data, max_lines=8))
    
    return '\n'.join(lines)