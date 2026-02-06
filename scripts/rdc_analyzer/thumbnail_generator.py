#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thumbnail Generator - 纹理缩略图生成器

从 RenderDoc ZIP+XML 导出中提取纹理并生成缩略图。

工作流程:
1. 解析 XML 建立资源映射 (Image -> Memory -> InitialContents)
2. 从 ZIP 中提取原始纹理数据
3. 使用 decoders 模块解码压缩格式
4. 生成缩略图 (PNG/Base64)

使用方法:
    from thumbnail_generator import ThumbnailGenerator
    
    gen = ThumbnailGenerator(xml_path, zip_path)
    thumbnails = gen.generate_thumbnails(max_count=20, max_size=128)
    # thumbnails = [{'id': 123, 'base64': 'data:image/png;base64,...', 'width': 128, ...}, ...]
"""

import base64
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 尝试导入解码器模块
try:
    from decoders import decode_texture, get_supported_formats, TextureDecodeError
    DECODER_AVAILABLE = True
except ImportError:
    try:
        from .decoders import decode_texture, get_supported_formats, TextureDecodeError
        DECODER_AVAILABLE = True
    except ImportError:
        DECODER_AVAILABLE = False
        logger.warning("Decoder module not available - thumbnails will be disabled")

# 尝试导入 Pillow
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not available - thumbnails will be disabled")


@dataclass
class ImageInfo:
    """纹理元数据"""
    resource_id: int
    width: int
    height: int
    depth: int
    format: str
    format_id: int
    image_type: str
    mip_levels: int = 1
    array_layers: int = 1


@dataclass
class MemoryBinding:
    """图像到内存的绑定"""
    image_id: int
    memory_id: int
    offset: int


@dataclass
class InitialContents:
    """内存初始内容"""
    resource_type: str
    resource_id: int
    is_sparse: bool
    contents_size: int
    buffer_index: int


@dataclass
class ThumbnailResult:
    """缩略图生成结果"""
    resource_id: int
    width: int
    height: int
    format: str
    thumbnail_width: int
    thumbnail_height: int
    base64_data: str  # data:image/png;base64,...
    success: bool
    error: str = ""


class ThumbnailGenerator:
    """
    纹理缩略图生成器
    
    从 RenderDoc ZIP+XML 导出中提取纹理并生成缩略图。
    """
    
    def __init__(self, xml_path: Path, zip_path: Optional[Path] = None):
        """
        初始化生成器
        
        Args:
            xml_path: XML 文件路径
            zip_path: ZIP 文件路径（如果未指定，自动推断）
        """
        self.xml_path = Path(xml_path)
        
        # 推断 ZIP 路径
        if zip_path:
            self.zip_path = Path(zip_path)
        else:
            self.zip_path = self._find_zip_path()
        
        self.images: Dict[int, ImageInfo] = {}
        self.bindings: List[MemoryBinding] = []
        self.initial_contents: Dict[int, InitialContents] = {}
        
        self._parsed = False
    
    def _find_zip_path(self) -> Path:
        """推断 ZIP 文件路径"""
        candidates = [
            self.xml_path.parent / self.xml_path.name.replace('.xml', ''),
            self.xml_path.with_suffix('.zip'),
            self.xml_path.with_suffix(''),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]  # 默认返回第一个（用于错误信息）
    
    def is_available(self) -> Tuple[bool, str]:
        """
        检查生成器是否可用
        
        Returns:
            (is_available, reason)
        """
        if not DECODER_AVAILABLE:
            return False, "Decoder module not available"
        if not PILLOW_AVAILABLE:
            return False, "Pillow not installed (pip install Pillow)"
        if not self.xml_path.exists():
            return False, f"XML file not found: {self.xml_path}"
        if not self.zip_path.exists():
            return False, f"ZIP file not found: {self.zip_path}"
        return True, "Ready"
    
    def parse(self) -> bool:
        """
        解析 XML 文件
        
        Returns:
            True if successful
        """
        if self._parsed:
            return True
        
        available, reason = self.is_available()
        if not available:
            logger.warning(f"ThumbnailGenerator not available: {reason}")
            return False
        
        logger.info(f"Parsing XML: {self.xml_path}")
        
        try:
            with open(self.xml_path, 'rb') as f:
                data = f.read()
            
            # 解析 vkCreateImage chunks
            self._parse_create_image(data)
            
            # 解析 vkBindImageMemory chunks
            self._parse_bind_image_memory(data)
            
            # 解析 InitialContents chunks
            self._parse_initial_contents(data)
            
            self._parsed = True
            logger.info(f"Parsed {len(self.images)} images, {len(self.bindings)} bindings, {len(self.initial_contents)} contents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            return False
    
    def _parse_create_image(self, data: bytes):
        """解析 vkCreateImage chunks"""
        pattern = rb'<chunk[^>]+name="vkCreateImage"[^>]*>(.*?)</chunk>'
        for match in re.finditer(pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            # 提取 Image ResourceId
            id_match = re.search(rb'<ResourceId[^>]+typename="VkImage"[^>]*>(\d+)</ResourceId>', chunk)
            if not id_match:
                continue
            image_id = int(id_match.group(1))
            
            # 提取 extent
            width_match = re.search(rb'<uint[^>]+name="width"[^>]*>(\d+)</uint>', chunk)
            height_match = re.search(rb'<uint[^>]+name="height"[^>]*>(\d+)</uint>', chunk)
            depth_match = re.search(rb'<uint[^>]+name="depth"[^>]*>(\d+)</uint>', chunk)
            
            # 提取 format
            format_match = re.search(rb'<enum[^>]+name="format"[^>]+string="([^"]+)"[^>]*>(\d+)</enum>', chunk)
            
            # 提取 imageType
            type_match = re.search(rb'<enum[^>]+name="imageType"[^>]+string="([^"]+)"', chunk)
            
            if width_match and height_match and depth_match:
                self.images[image_id] = ImageInfo(
                    resource_id=image_id,
                    width=int(width_match.group(1)),
                    height=int(height_match.group(1)),
                    depth=int(depth_match.group(1)),
                    format=format_match.group(1).decode() if format_match else 'UNKNOWN',
                    format_id=int(format_match.group(2)) if format_match else 0,
                    image_type=type_match.group(1).decode() if type_match else 'UNKNOWN',
                )
    
    def _parse_bind_image_memory(self, data: bytes):
        """解析 vkBindImageMemory chunks"""
        pattern = rb'<chunk[^>]+name="vkBindImageMemory"[^>]*>(.*?)</chunk>'
        for match in re.finditer(pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            image_match = re.search(rb'<ResourceId[^>]+name="image"[^>]*>(\d+)</ResourceId>', chunk)
            memory_match = re.search(rb'<ResourceId[^>]+name="memory"[^>]*>(\d+)</ResourceId>', chunk)
            offset_match = re.search(rb'<uint[^>]+name="memoryOffset"[^>]*>(\d+)</uint>', chunk)
            
            if image_match and memory_match and offset_match:
                self.bindings.append(MemoryBinding(
                    image_id=int(image_match.group(1)),
                    memory_id=int(memory_match.group(1)),
                    offset=int(offset_match.group(1)),
                ))
    
    def _parse_initial_contents(self, data: bytes):
        """解析 InitialContents chunks"""
        pattern = rb'<chunk[^>]+name="Internal::Initial Contents"[^>]*>(.*?)</chunk>'
        for match in re.finditer(pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            type_match = re.search(rb'<enum[^>]+name="type"[^>]+string="([^"]+)"', chunk)
            id_match = re.search(rb'<ResourceId[^>]+name="id"[^>]*>(\d+)</ResourceId>', chunk)
            sparse_match = re.search(rb'<bool[^>]+name="IsSparse"[^>]*>(true|false)</bool>', chunk)
            size_match = re.search(rb'<uint[^>]+name="ContentsSize"[^>]*>(\d+)</uint>', chunk)
            buffer_match = re.search(rb'<buffer[^>]+name="Contents"[^>]*>(\d+)</buffer>', chunk)
            
            if id_match and buffer_match:
                resource_id = int(id_match.group(1))
                self.initial_contents[resource_id] = InitialContents(
                    resource_type=type_match.group(1).decode() if type_match else 'Unknown',
                    resource_id=resource_id,
                    is_sparse=sparse_match.group(1) == b'true' if sparse_match else False,
                    contents_size=int(size_match.group(1)) if size_match else 0,
                    buffer_index=int(buffer_match.group(1)),
                )
    
    def get_extractable_textures(self) -> List[Tuple[ImageInfo, MemoryBinding, InitialContents]]:
        """
        获取所有可提取的纹理
        
        Returns:
            [(ImageInfo, MemoryBinding, InitialContents), ...]
        """
        if not self._parsed:
            self.parse()
        
        # 建立 image -> memory 映射
        image_to_memory = {b.image_id: b for b in self.bindings}
        
        extractable = []
        for img_id, img in self.images.items():
            binding = image_to_memory.get(img_id)
            if binding:
                ic = self.initial_contents.get(binding.memory_id)
                if ic:
                    extractable.append((img, binding, ic))
        
        # 按尺寸排序（大的优先）
        extractable.sort(key=lambda x: x[0].width * x[0].height, reverse=True)
        
        return extractable
    
    def generate_thumbnail(
        self,
        image_info: ImageInfo,
        binding: MemoryBinding,
        initial_content: InitialContents,
        max_size: int = 128
    ) -> ThumbnailResult:
        """
        生成单个纹理的缩略图
        
        Args:
            image_info: 纹理信息
            binding: 内存绑定
            initial_content: 初始内容
            max_size: 缩略图最大尺寸
        
        Returns:
            ThumbnailResult
        """
        # 读取原始数据
        buffer_name = f"{initial_content.buffer_index:06d}"
        
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                data = zf.read(buffer_name)
        except Exception as e:
            return ThumbnailResult(
                resource_id=image_info.resource_id,
                width=image_info.width,
                height=image_info.height,
                format=image_info.format,
                thumbnail_width=0,
                thumbnail_height=0,
                base64_data="",
                success=False,
                error=f"Failed to read buffer: {e}"
            )
        
        # 提取纹理数据（从 offset 开始）
        texture_data = data[binding.offset:] if binding.offset > 0 else data
        
        # 解码纹理
        try:
            rgba_data = decode_texture(
                texture_data,
                image_info.width,
                image_info.height,
                image_info.format
            )
        except TextureDecodeError as e:
            return ThumbnailResult(
                resource_id=image_info.resource_id,
                width=image_info.width,
                height=image_info.height,
                format=image_info.format,
                thumbnail_width=0,
                thumbnail_height=0,
                base64_data="",
                success=False,
                error=f"Decode failed: {e}"
            )
        except Exception as e:
            return ThumbnailResult(
                resource_id=image_info.resource_id,
                width=image_info.width,
                height=image_info.height,
                format=image_info.format,
                thumbnail_width=0,
                thumbnail_height=0,
                base64_data="",
                success=False,
                error=f"Unexpected error: {e}"
            )
        
        # 创建 PIL Image
        try:
            img = Image.frombytes('RGBA', (image_info.width, image_info.height), rgba_data)
            
            # 缩放到缩略图尺寸
            thumb_w, thumb_h = self._calc_thumbnail_size(
                image_info.width, image_info.height, max_size
            )
            img_thumb = img.resize((thumb_w, thumb_h), Image.LANCZOS)
            
            # 转换为 Base64
            buffer = io.BytesIO()
            img_thumb.save(buffer, format='PNG')
            base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return ThumbnailResult(
                resource_id=image_info.resource_id,
                width=image_info.width,
                height=image_info.height,
                format=image_info.format,
                thumbnail_width=thumb_w,
                thumbnail_height=thumb_h,
                base64_data=f"data:image/png;base64,{base64_data}",
                success=True
            )
            
        except Exception as e:
            return ThumbnailResult(
                resource_id=image_info.resource_id,
                width=image_info.width,
                height=image_info.height,
                format=image_info.format,
                thumbnail_width=0,
                thumbnail_height=0,
                base64_data="",
                success=False,
                error=f"Image processing failed: {e}"
            )
    
    def _calc_thumbnail_size(self, width: int, height: int, max_size: int) -> Tuple[int, int]:
        """计算缩略图尺寸（保持宽高比）"""
        if width <= max_size and height <= max_size:
            return width, height
        
        if width >= height:
            new_w = max_size
            new_h = int(height * max_size / width)
        else:
            new_h = max_size
            new_w = int(width * max_size / height)
        
        return max(1, new_w), max(1, new_h)
    
    def generate_thumbnails(
        self,
        max_count: int = 20,
        max_size: int = 128,
        min_texture_size: int = 64,
        skip_formats: Optional[List[str]] = None
    ) -> List[ThumbnailResult]:
        """
        批量生成缩略图
        
        Args:
            max_count: 最多生成多少个缩略图
            max_size: 缩略图最大尺寸
            min_texture_size: 跳过小于此尺寸的纹理
            skip_formats: 跳过的格式列表
        
        Returns:
            [ThumbnailResult, ...]
        """
        available, reason = self.is_available()
        if not available:
            logger.warning(f"Cannot generate thumbnails: {reason}")
            return []
        
        if not self._parsed:
            if not self.parse():
                return []
        
        extractable = self.get_extractable_textures()
        
        # 过滤
        skip_formats = skip_formats or []
        skip_formats_upper = [f.upper() for f in skip_formats]
        
        filtered = []
        for img, binding, ic in extractable:
            # 跳过太小的纹理
            if img.width < min_texture_size and img.height < min_texture_size:
                continue
            
            # 跳过指定格式
            if any(skip in img.format.upper() for skip in skip_formats_upper):
                continue
            
            # 跳过深度/模板纹理（通常不需要预览）
            if any(x in img.format.upper() for x in ['DEPTH', 'STENCIL', 'D32', 'D24', 'D16']):
                continue
            
            filtered.append((img, binding, ic))
        
        # 限制数量
        filtered = filtered[:max_count]
        
        logger.info(f"Generating {len(filtered)} thumbnails...")
        
        results = []
        for img, binding, ic in filtered:
            result = self.generate_thumbnail(img, binding, ic, max_size)
            results.append(result)
            
            if result.success:
                logger.debug(f"  ✓ {img.resource_id}: {img.width}x{img.height} {img.format}")
            else:
                logger.debug(f"  ✗ {img.resource_id}: {result.error}")
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Generated {success_count}/{len(results)} thumbnails successfully")
        
        return results


def generate_thumbnails_for_report(
    xml_path: Path,
    texture_data: List[dict],
    max_count: int = 20,
    max_size: int = 128
) -> Dict[int, str]:
    """
    便捷函数: 为报告生成缩略图
    
    Args:
        xml_path: XML 文件路径
        texture_data: 纹理列表 (来自分析器)
        max_count: 最多生成多少个
        max_size: 缩略图最大尺寸
    
    Returns:
        {resource_id: base64_data, ...}
    """
    gen = ThumbnailGenerator(xml_path)
    
    available, reason = gen.is_available()
    if not available:
        logger.info(f"Thumbnails disabled: {reason}")
        return {}
    
    results = gen.generate_thumbnails(max_count=max_count, max_size=max_size)
    
    return {r.resource_id: r.base64_data for r in results if r.success}


if __name__ == '__main__':
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) < 2:
        print("Usage: py -3 thumbnail_generator.py <xml_file> [--test]")
        sys.exit(1)
    
    xml_path = Path(sys.argv[1])
    
    gen = ThumbnailGenerator(xml_path)
    available, reason = gen.is_available()
    print(f"Available: {available} - {reason}")
    
    if available and '--test' in sys.argv:
        results = gen.generate_thumbnails(max_count=5, max_size=64)
        for r in results:
            status = "✓" if r.success else "✗"
            print(f"  {status} ID={r.resource_id} {r.width}x{r.height} {r.format}")
            if r.success:
                print(f"      Thumbnail: {r.thumbnail_width}x{r.thumbnail_height}, {len(r.base64_data)} chars")
            else:
                print(f"      Error: {r.error}")
