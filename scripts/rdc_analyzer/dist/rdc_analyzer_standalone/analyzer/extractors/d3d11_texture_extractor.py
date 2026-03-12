#!/usr/bin/env python3
"""
d3d11_texture_extractor.py - D3D11 纹理提取引擎

从 D3D11 RDC 导出的 XML+ZIP 中提取纹理数据。

架构简化:
- D3D11 不需要 VkDeviceMemory 映射，InitialContents 直接存储在纹理资源 ID 上
- 每个子资源（Mip Level × Array Slice）有独立的 buffer 索引

使用方法:
    from extractors.d3d11_texture_extractor import D3D11TextureExtractor
    
    extractor = D3D11TextureExtractor(xml_path, zip_path, output_dir)
    extractor.extract_all()
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zipfile import ZipFile

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.d3d11_texture_parser import (
    D3D11TextureInfo,
    D3D11SubresourceData,
    parse_d3d11_xml,
    detect_api_type,
)
from decoders.dxgi_format_map import (
    DXGI_FORMAT_MAP,
    get_bytes_per_pixel,
    get_block_size,
    is_compressed_format,
    is_depth_format,
)
from decoders.texture_decoder import decode_texture


class D3D11TextureExtractor:
    """D3D11 纹理提取器"""
    
    def __init__(
        self,
        xml_path: Path,
        zip_path: Path,
        output_dir: Path,
        verbose: bool = False
    ):
        """
        初始化提取器
        
        Args:
            xml_path: XML 文件路径
            zip_path: ZIP 文件路径
            output_dir: 输出目录
            verbose: 是否显示详细信息
        """
        self.xml_path = Path(xml_path)
        self.zip_path = Path(zip_path)
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        
        self.textures: Dict[int, D3D11TextureInfo] = {}
        self.api_type: str = ""
        self._zip: Optional[ZipFile] = None
        self._zip_namelist: List[str] = []
        
        # 统计
        self.stats = {
            "total": 0,
            "extracted": 0,
            "skipped": 0,
            "failed": 0,
        }
    
    def parse(self) -> bool:
        """
        解析 XML 文件
        
        Returns:
            是否成功
        """
        if not self.xml_path.exists():
            print(f"[!] XML file not found: {self.xml_path}")
            return False
        
        self.textures, self.api_type = parse_d3d11_xml(self.xml_path)
        
        if self.api_type != "D3D11":
            print(f"[!] Not a D3D11 capture. Detected: {self.api_type}")
            return False
        
        self.stats["total"] = len(self.textures)
        return len(self.textures) > 0
    
    def open_zip(self) -> bool:
        """
        打开 ZIP 文件
        
        Returns:
            是否成功
        """
        if not self.zip_path.exists():
            print(f"[!] ZIP file not found: {self.zip_path}")
            return False
        
        try:
            self._zip = ZipFile(self.zip_path, 'r')
            self._zip_namelist = self._zip.namelist()
            print(f"[*] ZIP contains {len(self._zip_namelist)} files")
            return True
        except Exception as e:
            print(f"[!] Failed to open ZIP: {e}")
            return False
    
    def close_zip(self) -> None:
        """关闭 ZIP 文件"""
        if self._zip:
            self._zip.close()
            self._zip = None
    
    def _read_buffer(self, buffer_index: int) -> Optional[bytes]:
        """
        从 ZIP 中读取 buffer
        
        Args:
            buffer_index: buffer 索引
        
        Returns:
            buffer 数据或 None
        """
        if not self._zip:
            return None
        
        # RenderDoc ZIP 格式: "buffers/buffer{index}"
        buffer_name = f"buffers/buffer{buffer_index}"
        
        if buffer_name not in self._zip_namelist:
            if self.verbose:
                print(f"    [!] Buffer not found: {buffer_name}")
            return None
        
        try:
            return self._zip.read(buffer_name)
        except Exception as e:
            print(f"    [!] Failed to read buffer {buffer_index}: {e}")
            return None
    
    def extract_texture(
        self,
        tex: D3D11TextureInfo,
        mip_level: int = 0
    ) -> Optional[bytes]:
        """
        提取单个纹理的指定 mip 级别
        
        Args:
            tex: 纹理信息
            mip_level: mip 级别 (默认 0 = 最大分辨率)
        
        Returns:
            PNG 数据或 None
        """
        if not tex.has_initial_contents:
            if self.verbose:
                print(f"    [!] No initial contents for texture {tex.resource_id}")
            return None
        
        # 找到对应的子资源
        subresource_index = tex.get_subresource_index(mip_level, array_slice=0)
        
        if subresource_index >= len(tex.subresources):
            if self.verbose:
                print(f"    [!] Subresource {subresource_index} not found")
            return None
        
        subres = tex.subresources[subresource_index]
        
        # 读取 buffer
        raw_data = self._read_buffer(subres.buffer_index)
        if not raw_data:
            return None
        
        # 获取 mip 尺寸
        width, height, depth = tex.get_mip_dimensions(mip_level)
        
        # 解码
        try:
            png_data = decode_texture(
                raw_data=raw_data,
                width=width,
                height=height,
                format_name=tex.format,
                row_pitch=subres.row_pitch,
            )
            return png_data
        except Exception as e:
            if self.verbose:
                print(f"    [!] Decode failed: {e}")
            return None
    
    def extract_all(
        self,
        min_size: int = 32,
        max_count: int = 0,
        formats: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        批量提取所有纹理
        
        Args:
            min_size: 最小尺寸 (宽或高)
            max_count: 最大数量 (0 = 无限制)
            formats: 仅提取指定格式 (None = 所有)
        
        Returns:
            统计信息
        """
        if not self.textures:
            print("[!] No textures parsed. Call parse() first.")
            return self.stats
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 打开 ZIP
        if not self.open_zip():
            return self.stats
        
        try:
            # 筛选可提取的纹理
            extractable = [
                tex for tex in self.textures.values()
                if tex.has_initial_contents
                and tex.width >= min_size
                and tex.height >= min_size
                and (formats is None or tex.format in formats)
            ]
            
            # 按尺寸排序
            extractable.sort(key=lambda t: t.width * t.height, reverse=True)
            
            if max_count > 0:
                extractable = extractable[:max_count]
            
            print(f"\n[*] Extracting {len(extractable)} textures...")
            
            for i, tex in enumerate(extractable):
                self._extract_one(tex, i + 1, len(extractable))
            
        finally:
            self.close_zip()
        
        # 打印统计
        print(f"\n{'='*60}")
        print(f"Extraction Complete")
        print(f"{'='*60}")
        print(f"  Total:     {self.stats['total']}")
        print(f"  Extracted: {self.stats['extracted']}")
        print(f"  Skipped:   {self.stats['skipped']}")
        print(f"  Failed:    {self.stats['failed']}")
        print(f"  Output:    {self.output_dir}")
        
        return self.stats
    
    def _extract_one(self, tex: D3D11TextureInfo, index: int, total: int) -> bool:
        """提取单个纹理"""
        
        # 生成文件名
        format_short = tex.format.replace("DXGI_FORMAT_", "")
        filename = f"tex_{tex.resource_id:05d}_{tex.width}x{tex.height}_{format_short}.png"
        output_path = self.output_dir / filename
        
        print(f"  [{index}/{total}] {filename}", end=" ")
        
        # 跳过深度格式
        if is_depth_format(tex.format):
            print("[SKIP: depth]")
            self.stats["skipped"] += 1
            return False
        
        # 检查格式是否支持
        if tex.format not in DXGI_FORMAT_MAP:
            print(f"[SKIP: unsupported format]")
            self.stats["skipped"] += 1
            return False
        
        # 提取
        png_data = self.extract_texture(tex, mip_level=0)
        
        if png_data:
            output_path.write_bytes(png_data)
            print(f"[OK: {len(png_data)/1024:.1f}KB]")
            self.stats["extracted"] += 1
            return True
        else:
            print("[FAILED]")
            self.stats["failed"] += 1
            return False


def extract_d3d11_textures(
    xml_path: str,
    zip_path: str,
    output_dir: str,
    min_size: int = 32,
    max_count: int = 0,
    verbose: bool = False,
) -> Dict[str, any]:
    """
    便捷函数：提取 D3D11 纹理
    
    Args:
        xml_path: XML 文件路径
        zip_path: ZIP 文件路径
        output_dir: 输出目录
        min_size: 最小尺寸
        max_count: 最大数量
        verbose: 详细输出
    
    Returns:
        统计信息
    """
    extractor = D3D11TextureExtractor(
        xml_path=Path(xml_path),
        zip_path=Path(zip_path),
        output_dir=Path(output_dir),
        verbose=verbose,
    )
    
    if not extractor.parse():
        return extractor.stats
    
    return extractor.extract_all(
        min_size=min_size,
        max_count=max_count,
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract textures from D3D11 RDC exports"
    )
    parser.add_argument("xml_file", help="Path to XML file")
    parser.add_argument("zip_file", help="Path to ZIP file")
    parser.add_argument("-o", "--output", default="./d3d11_textures",
                        help="Output directory")
    parser.add_argument("-m", "--min-size", type=int, default=32,
                        help="Minimum texture size")
    parser.add_argument("-n", "--max-count", type=int, default=0,
                        help="Maximum number of textures (0=all)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    
    args = parser.parse_args()
    
    extract_d3d11_textures(
        xml_path=args.xml_file,
        zip_path=args.zip_file,
        output_dir=args.output,
        min_size=args.min_size,
        max_count=args.max_count,
        verbose=args.verbose,
    )
