#!/usr/bin/env python3
"""
d3d11_texture_parser.py - D3D11 RDC XML 纹理解析器

从 RenderDoc 导出的 D3D11 XML 文件中解析纹理信息。

D3D11 与 Vulkan 的关键区别:
- D3D11: CreateTexture2D → InitialContents 直接存储数据 (无内存绑定)
- Vulkan: vkCreateImage → vkBindImageMemory → InitialContents(DeviceMemory)

使用方法:
    from parsers.d3d11_texture_parser import parse_d3d11_xml, D3D11TextureInfo
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 尝试导入 DXGI 格式映射
try:
    from decoders.dxgi_format_map import get_bytes_per_pixel, is_compressed_format
except ImportError:
    def get_bytes_per_pixel(fmt: str) -> float:
        return 4.0
    def is_compressed_format(fmt: str) -> bool:
        return "BC" in fmt


@dataclass
class D3D11SubresourceData:
    """D3D11 子资源数据"""
    subresource_index: int      # 子资源索引 (mip * array_size + array_slice)
    row_pitch: int              # 行间距
    buffer_index: int           # ZIP 中的 buffer 索引
    data_size: int = 0          # 数据大小


@dataclass
class D3D11TextureInfo:
    """D3D11 纹理元数据"""
    resource_id: int            # 资源 ID
    width: int                  # 宽度
    height: int                 # 高度
    depth: int = 1              # 深度 (3D 纹理)
    mip_levels: int = 1         # Mip 级别数
    array_size: int = 1         # 数组大小
    format: str = ""            # DXGI 格式 (如 "DXGI_FORMAT_BC7_UNORM")
    format_id: int = 0          # 格式枚举值
    sample_count: int = 1       # MSAA 采样数
    sample_quality: int = 0     # MSAA 质量
    usage: str = ""             # D3D11_USAGE
    bind_flags: str = ""        # 绑定标志
    texture_type: str = "2D"    # "2D" 或 "3D"
    
    # InitialContents 数据
    subresources: List[D3D11SubresourceData] = field(default_factory=list)
    has_initial_contents: bool = False
    
    def get_mip_dimensions(self, mip_level: int) -> Tuple[int, int, int]:
        """获取指定 mip 级别的尺寸"""
        w = max(1, self.width >> mip_level)
        h = max(1, self.height >> mip_level)
        d = max(1, self.depth >> mip_level)
        return (w, h, d)
    
    def get_subresource_index(self, mip_level: int, array_slice: int = 0) -> int:
        """计算子资源索引"""
        return mip_level + (array_slice * self.mip_levels)
    
    def estimate_size(self) -> int:
        """估算纹理总大小"""
        bpp = get_bytes_per_pixel(self.format)
        is_bc = is_compressed_format(self.format)
        
        total = 0
        for mip in range(self.mip_levels):
            w, h, d = self.get_mip_dimensions(mip)
            
            if is_bc:
                block_w = (w + 3) // 4
                block_h = (h + 3) // 4
                block_size = int(bpp * 16)
                mip_size = block_w * block_h * block_size * d
            else:
                mip_size = int(w * h * d * bpp)
            
            total += mip_size * self.array_size
        
        return total


def detect_api_type(xml_data: bytes) -> str:
    """
    检测 RDC XML 的图形 API 类型
    
    Args:
        xml_data: XML 文件内容
    
    Returns:
        "D3D11", "D3D12", "Vulkan", "OpenGL" 或 "Unknown"
    """
    # D3D11 特征
    if b'ID3D11Device::CreateTexture2D' in xml_data:
        return "D3D11"
    if b'ID3D11Device3::CreateTexture2D1' in xml_data:
        return "D3D11"
    
    # D3D12 特征
    if b'ID3D12Device::CreateCommittedResource' in xml_data:
        return "D3D12"
    
    # Vulkan 特征
    if b'vkCreateImage' in xml_data:
        return "Vulkan"
    
    # OpenGL 特征
    if b'glTexImage2D' in xml_data or b'glTextureStorage2D' in xml_data:
        return "OpenGL"
    
    return "Unknown"


def parse_d3d11_textures(xml_data: bytes) -> Dict[int, D3D11TextureInfo]:
    """
    解析 D3D11 CreateTexture2D 和 CreateTexture3D chunks
    
    Args:
        xml_data: XML 文件内容
    
    Returns:
        {resource_id: D3D11TextureInfo} 字典
    """
    textures: Dict[int, D3D11TextureInfo] = {}
    
    # 解析 CreateTexture2D
    # 匹配模式：<chunk ... name="ID3D11Device::CreateTexture2D" ...>...</chunk>
    tex2d_pattern = rb'<chunk[^>]+name="ID3D11Device::CreateTexture2D"[^>]*>(.*?)</chunk>'
    
    for match in re.finditer(tex2d_pattern, xml_data, re.DOTALL):
        chunk_content = match.group(1)
        tex_info = _parse_texture2d_chunk(chunk_content)
        if tex_info:
            textures[tex_info.resource_id] = tex_info
    
    # 解析 CreateTexture2D1 (D3D11.3+)
    tex2d1_pattern = rb'<chunk[^>]+name="ID3D11Device3::CreateTexture2D1"[^>]*>(.*?)</chunk>'
    
    for match in re.finditer(tex2d1_pattern, xml_data, re.DOTALL):
        chunk_content = match.group(1)
        tex_info = _parse_texture2d_chunk(chunk_content)
        if tex_info:
            textures[tex_info.resource_id] = tex_info
    
    # 解析 CreateTexture3D
    tex3d_pattern = rb'<chunk[^>]+name="ID3D11Device::CreateTexture3D"[^>]*>(.*?)</chunk>'
    
    for match in re.finditer(tex3d_pattern, xml_data, re.DOTALL):
        chunk_content = match.group(1)
        tex_info = _parse_texture3d_chunk(chunk_content)
        if tex_info:
            textures[tex_info.resource_id] = tex_info
    
    return textures


def _parse_texture2d_chunk(chunk_content: bytes) -> Optional[D3D11TextureInfo]:
    """解析单个 CreateTexture2D chunk"""
    
    # 提取返回的纹理资源 ID
    # 格式: <ResourceId ... name="pTexture" ...>12345</ResourceId>
    res_id_match = re.search(
        rb'<ResourceId[^>]+name="pTexture"[^>]*>(\d+)</ResourceId>',
        chunk_content
    )
    if not res_id_match:
        # 尝试其他可能的名称
        res_id_match = re.search(
            rb'<ResourceId[^>]+typename="ID3D11Texture2D"[^>]*>(\d+)</ResourceId>',
            chunk_content
        )
    if not res_id_match:
        return None
    
    resource_id = int(res_id_match.group(1))
    
    # 提取 Width
    width_match = re.search(rb'<uint[^>]+name="Width"[^>]*>(\d+)</uint>', chunk_content)
    width = int(width_match.group(1)) if width_match else 0
    
    # 提取 Height
    height_match = re.search(rb'<uint[^>]+name="Height"[^>]*>(\d+)</uint>', chunk_content)
    height = int(height_match.group(1)) if height_match else 0
    
    # 提取 MipLevels
    mip_match = re.search(rb'<uint[^>]+name="MipLevels"[^>]*>(\d+)</uint>', chunk_content)
    mip_levels = int(mip_match.group(1)) if mip_match else 1
    
    # 提取 ArraySize
    array_match = re.search(rb'<uint[^>]+name="ArraySize"[^>]*>(\d+)</uint>', chunk_content)
    array_size = int(array_match.group(1)) if array_match else 1
    
    # 提取 Format
    # 格式: <enum ... name="Format" ... string="DXGI_FORMAT_BC7_UNORM">98</enum>
    format_match = re.search(
        rb'<enum[^>]+name="Format"[^>]+string="([^"]+)"[^>]*>(\d+)</enum>',
        chunk_content
    )
    format_str = format_match.group(1).decode() if format_match else "UNKNOWN"
    format_id = int(format_match.group(2)) if format_match else 0
    
    # 提取 SampleDesc.Count
    sample_count_match = re.search(
        rb'<uint[^>]+name="Count"[^>]*>(\d+)</uint>',
        chunk_content
    )
    sample_count = int(sample_count_match.group(1)) if sample_count_match else 1
    
    # 提取 Usage
    usage_match = re.search(
        rb'<enum[^>]+name="Usage"[^>]+string="([^"]+)"',
        chunk_content
    )
    usage = usage_match.group(1).decode() if usage_match else ""
    
    # 提取 BindFlags
    bind_match = re.search(
        rb'<enum[^>]+name="BindFlags"[^>]+string="([^"]+)"',
        chunk_content
    )
    bind_flags = bind_match.group(1).decode() if bind_match else ""
    
    return D3D11TextureInfo(
        resource_id=resource_id,
        width=width,
        height=height,
        depth=1,
        mip_levels=mip_levels,
        array_size=array_size,
        format=format_str,
        format_id=format_id,
        sample_count=sample_count,
        usage=usage,
        bind_flags=bind_flags,
        texture_type="2D",
    )


def _parse_texture3d_chunk(chunk_content: bytes) -> Optional[D3D11TextureInfo]:
    """解析单个 CreateTexture3D chunk"""
    
    # 提取返回的纹理资源 ID
    res_id_match = re.search(
        rb'<ResourceId[^>]+name="pTexture"[^>]*>(\d+)</ResourceId>',
        chunk_content
    )
    if not res_id_match:
        res_id_match = re.search(
            rb'<ResourceId[^>]+typename="ID3D11Texture3D"[^>]*>(\d+)</ResourceId>',
            chunk_content
        )
    if not res_id_match:
        return None
    
    resource_id = int(res_id_match.group(1))
    
    # 提取 Width, Height, Depth
    width_match = re.search(rb'<uint[^>]+name="Width"[^>]*>(\d+)</uint>', chunk_content)
    height_match = re.search(rb'<uint[^>]+name="Height"[^>]*>(\d+)</uint>', chunk_content)
    depth_match = re.search(rb'<uint[^>]+name="Depth"[^>]*>(\d+)</uint>', chunk_content)
    
    width = int(width_match.group(1)) if width_match else 0
    height = int(height_match.group(1)) if height_match else 0
    depth = int(depth_match.group(1)) if depth_match else 1
    
    # 提取 MipLevels
    mip_match = re.search(rb'<uint[^>]+name="MipLevels"[^>]*>(\d+)</uint>', chunk_content)
    mip_levels = int(mip_match.group(1)) if mip_match else 1
    
    # 提取 Format
    format_match = re.search(
        rb'<enum[^>]+name="Format"[^>]+string="([^"]+)"[^>]*>(\d+)</enum>',
        chunk_content
    )
    format_str = format_match.group(1).decode() if format_match else "UNKNOWN"
    format_id = int(format_match.group(2)) if format_match else 0
    
    return D3D11TextureInfo(
        resource_id=resource_id,
        width=width,
        height=height,
        depth=depth,
        mip_levels=mip_levels,
        array_size=1,  # 3D 纹理没有数组
        format=format_str,
        format_id=format_id,
        texture_type="3D",
    )


def parse_d3d11_initial_contents(
    xml_data: bytes,
    textures: Dict[int, D3D11TextureInfo]
) -> Dict[int, D3D11TextureInfo]:
    """
    解析 D3D11 InitialContents，关联到纹理
    
    D3D11 的 InitialContents 结构:
    <chunk name="Internal::Initial Contents">
        <ResourceId name="id">123</ResourceId>
        <uint name="NumSubresources">11</uint>
        <bool name="OmittedContents">false</bool>
        
        <!-- 每个子资源 -->
        <uint name="RowPitch">8192</uint>
        <buffer name="SubresourceContents">45</buffer>
        ...
    </chunk>
    
    Args:
        xml_data: XML 文件内容
        textures: 已解析的纹理字典
    
    Returns:
        更新后的纹理字典
    """
    
    # D3D11 的 InitialContents 直接存储在纹理资源 ID 上（不像 Vulkan 需要内存绑定）
    ic_pattern = rb'<chunk[^>]+name="Internal::Initial Contents"[^>]*>(.*?)</chunk>'
    
    for match in re.finditer(ic_pattern, xml_data, re.DOTALL):
        chunk_content = match.group(1)
        
        # 提取资源 ID
        id_match = re.search(rb'<ResourceId[^>]+name="id"[^>]*>(\d+)</ResourceId>', chunk_content)
        if not id_match:
            continue
        
        resource_id = int(id_match.group(1))
        
        # 检查是否为已知纹理
        if resource_id not in textures:
            continue
        
        tex = textures[resource_id]
        
        # 提取 NumSubresources
        num_sub_match = re.search(
            rb'<uint[^>]+name="NumSubresources"[^>]*>(\d+)</uint>',
            chunk_content
        )
        num_subresources = int(num_sub_match.group(1)) if num_sub_match else 0
        
        # 检查是否省略了内容
        omit_match = re.search(
            rb'<bool[^>]+name="OmittedContents"[^>]*>(true|false)</bool>',
            chunk_content
        )
        if omit_match and omit_match.group(1) == b'true':
            continue
        
        # 解析每个子资源的 RowPitch 和 buffer
        # 注意: D3D11 的结构是交替的 RowPitch + SubresourceContents
        row_pitch_pattern = rb'<uint[^>]+name="RowPitch"[^>]*>(\d+)</uint>'
        buffer_pattern = rb'<buffer[^>]+name="SubresourceContents"[^>]*>(\d+)</buffer>'
        
        row_pitches = [int(m.group(1)) for m in re.finditer(row_pitch_pattern, chunk_content)]
        buffer_indices = [int(m.group(1)) for m in re.finditer(buffer_pattern, chunk_content)]
        
        # 配对
        for i, (pitch, buf_idx) in enumerate(zip(row_pitches, buffer_indices)):
            tex.subresources.append(D3D11SubresourceData(
                subresource_index=i,
                row_pitch=pitch,
                buffer_index=buf_idx,
            ))
        
        tex.has_initial_contents = len(tex.subresources) > 0
    
    return textures


def parse_d3d11_xml(xml_path: Path) -> Tuple[Dict[int, D3D11TextureInfo], str]:
    """
    解析 D3D11 RDC XML 文件
    
    Args:
        xml_path: XML 文件路径
    
    Returns:
        (textures_dict, api_type)
    """
    print(f"[*] Parsing D3D11 XML: {xml_path}")
    file_size = xml_path.stat().st_size
    print(f"    File size: {file_size / 1024 / 1024:.2f} MB")
    
    print("    Loading file...")
    with open(xml_path, 'rb') as f:
        data = f.read()
    
    # 检测 API 类型
    api_type = detect_api_type(data)
    print(f"    Detected API: {api_type}")
    
    if api_type != "D3D11":
        print(f"    Warning: This parser is for D3D11, but detected {api_type}")
        return {}, api_type
    
    # 解析纹理创建
    print("    Parsing CreateTexture2D/3D...")
    textures = parse_d3d11_textures(data)
    print(f"    Found {len(textures)} textures")
    
    # 解析 InitialContents
    print("    Parsing InitialContents...")
    textures = parse_d3d11_initial_contents(data, textures)
    
    extractable = sum(1 for t in textures.values() if t.has_initial_contents)
    print(f"    Extractable: {extractable} / {len(textures)}")
    
    return textures, api_type


def list_d3d11_textures(textures: Dict[int, D3D11TextureInfo]) -> None:
    """打印 D3D11 纹理列表"""
    
    print("\n" + "=" * 90)
    print("D3D11 TEXTURES")
    print("=" * 90)
    
    # 按尺寸排序
    sorted_textures = sorted(
        textures.values(),
        key=lambda t: t.width * t.height,
        reverse=True
    )
    
    extractable = [t for t in sorted_textures if t.has_initial_contents]
    
    print(f"\nFound {len(extractable)} extractable textures out of {len(textures)} total\n")
    
    print(f"{'ID':>8} {'Size':>12} {'Mips':>5} {'Arr':>4} {'Format':<30} {'Extract':>8}")
    print("-" * 90)
    
    for tex in sorted_textures[:50]:  # 只显示前 50 个
        size_str = f"{tex.width}x{tex.height}"
        if tex.depth > 1:
            size_str += f"x{tex.depth}"
        
        status = "✓" if tex.has_initial_contents else "-"
        
        print(f"{tex.resource_id:>8} {size_str:>12} {tex.mip_levels:>5} "
              f"{tex.array_size:>4} {tex.format:<30} {status:>8}")
    
    if len(sorted_textures) > 50:
        print(f"\n... and {len(sorted_textures) - 50} more textures")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: py -3 d3d11_texture_parser.py <xml_file>")
        sys.exit(1)
    
    xml_path = Path(sys.argv[1])
    if not xml_path.exists():
        print(f"Error: File not found: {xml_path}")
        sys.exit(1)
    
    textures, api_type = parse_d3d11_xml(xml_path)
    
    if textures:
        list_d3d11_textures(textures)
    else:
        print(f"No D3D11 textures found. Detected API: {api_type}")
