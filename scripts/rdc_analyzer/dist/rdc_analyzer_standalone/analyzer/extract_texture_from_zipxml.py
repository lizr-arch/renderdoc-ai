#!/usr/bin/env python3
"""
extract_texture_from_zipxml.py - 从 RenderDoc XML+ZIP 导出中提取纹理数据

工作流程：
1. 使用 renderdoccmd convert -c zip.xml 将 RDC 转换为 XML + ZIP
2. 本脚本解析 XML 建立资源映射关系
3. 从 ZIP 中提取对应 buffer 的像素数据

使用方法：
    py -3 extract_texture_from_zipxml.py <xml_file> [--list-textures] [--extract <image_id>]

依赖：仅标准库（无需 renderdoc.pyd）
"""

import argparse
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# 尝试导入解码器模块
try:
    from decoders import decode_texture, save_as_png, get_supported_formats, TextureDecodeError
    DECODER_AVAILABLE = True
except ImportError:
    DECODER_AVAILABLE = False


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


def parse_xml_regex(xml_path: Path) -> tuple:
    """
    使用正则表达式解析 XML 文件（更快，内存效率更高）
    
    Returns:
        (images, bindings, initial_contents)
    """
    print(f"[*] Parsing XML: {xml_path}")
    file_size = xml_path.stat().st_size
    print(f"    File size: {file_size / 1024 / 1024:.2f} MB")
    
    images: Dict[int, ImageInfo] = {}
    bindings: List[MemoryBinding] = []
    initial_contents: Dict[int, InitialContents] = {}
    
    # 读取整个文件
    print("    Loading file...")
    with open(xml_path, 'rb') as f:
        data = f.read()
    
    print("    Parsing vkCreateImage...")
    # 解析 vkCreateImage chunks
    # 匹配模式：<chunk ... name="vkCreateImage" ...>...</chunk>
    create_image_pattern = rb'<chunk[^>]+name="vkCreateImage"[^>]*>(.*?)</chunk>'
    for match in re.finditer(create_image_pattern, data, re.DOTALL):
        chunk_content = match.group(1)
        
        # 提取 Image ResourceId
        image_id_match = re.search(rb'<ResourceId[^>]+typename="VkImage"[^>]*>(\d+)</ResourceId>', chunk_content)
        if not image_id_match:
            continue
        image_id = int(image_id_match.group(1))
        
        # 提取 extent
        width_match = re.search(rb'<uint[^>]+name="width"[^>]*>(\d+)</uint>', chunk_content)
        height_match = re.search(rb'<uint[^>]+name="height"[^>]*>(\d+)</uint>', chunk_content)
        depth_match = re.search(rb'<uint[^>]+name="depth"[^>]*>(\d+)</uint>', chunk_content)
        
        # 提取 format
        format_match = re.search(rb'<enum[^>]+name="format"[^>]+string="([^"]+)"[^>]*>(\d+)</enum>', chunk_content)
        
        # 提取 imageType
        type_match = re.search(rb'<enum[^>]+name="imageType"[^>]+string="([^"]+)"', chunk_content)
        
        if width_match and height_match and depth_match:
            images[image_id] = ImageInfo(
                resource_id=image_id,
                width=int(width_match.group(1)),
                height=int(height_match.group(1)),
                depth=int(depth_match.group(1)),
                format=format_match.group(1).decode() if format_match else 'UNKNOWN',
                format_id=int(format_match.group(2)) if format_match else 0,
                image_type=type_match.group(1).decode() if type_match else 'UNKNOWN',
            )
    
    print(f"    Found {len(images)} images")
    
    print("    Parsing vkBindImageMemory...")
    # 解析 vkBindImageMemory chunks
    bind_pattern = rb'<chunk[^>]+name="vkBindImageMemory"[^>]*>(.*?)</chunk>'
    for match in re.finditer(bind_pattern, data, re.DOTALL):
        chunk_content = match.group(1)
        
        # 提取 image, memory, offset
        image_match = re.search(rb'<ResourceId[^>]+name="image"[^>]*>(\d+)</ResourceId>', chunk_content)
        memory_match = re.search(rb'<ResourceId[^>]+name="memory"[^>]*>(\d+)</ResourceId>', chunk_content)
        offset_match = re.search(rb'<uint[^>]+name="memoryOffset"[^>]*>(\d+)</uint>', chunk_content)
        
        if image_match and memory_match and offset_match:
            bindings.append(MemoryBinding(
                image_id=int(image_match.group(1)),
                memory_id=int(memory_match.group(1)),
                offset=int(offset_match.group(1)),
            ))
    
    print(f"    Found {len(bindings)} bindings")
    
    print("    Parsing InitialContents...")
    # 解析 Internal::Initial Contents chunks
    ic_pattern = rb'<chunk[^>]+name="Internal::Initial Contents"[^>]*>(.*?)</chunk>'
    for match in re.finditer(ic_pattern, data, re.DOTALL):
        chunk_content = match.group(1)
        
        # 提取 type
        type_match = re.search(rb'<enum[^>]+name="type"[^>]+string="([^"]+)"', chunk_content)
        
        # 提取 id
        id_match = re.search(rb'<ResourceId[^>]+name="id"[^>]*>(\d+)</ResourceId>', chunk_content)
        
        # 提取 IsSparse
        sparse_match = re.search(rb'<bool[^>]+name="IsSparse"[^>]*>(true|false)</bool>', chunk_content)
        
        # 提取 ContentsSize
        size_match = re.search(rb'<uint[^>]+name="ContentsSize"[^>]*>(\d+)</uint>', chunk_content)
        
        # 提取 buffer index
        buffer_match = re.search(rb'<buffer[^>]+name="Contents"[^>]*>(\d+)</buffer>', chunk_content)
        
        if id_match and buffer_match:
            resource_id = int(id_match.group(1))
            initial_contents[resource_id] = InitialContents(
                resource_type=type_match.group(1).decode() if type_match else 'Unknown',
                resource_id=resource_id,
                is_sparse=sparse_match.group(1) == b'true' if sparse_match else False,
                contents_size=int(size_match.group(1)) if size_match else 0,
                buffer_index=int(buffer_match.group(1)),
            )
    
    print(f"    Found {len(initial_contents)} initial contents")
    
    return images, bindings, initial_contents


def list_textures(images: Dict[int, ImageInfo], 
                  bindings: List[MemoryBinding],
                  initial_contents: Dict[int, InitialContents]):
    """列出所有可提取的纹理"""
    
    print("\n" + "=" * 80)
    print("EXTRACTABLE TEXTURES")
    print("=" * 80)
    
    # 建立 image -> memory 映射
    image_to_memory = {b.image_id: b for b in bindings}
    
    extractable = []
    for img_id, img in sorted(images.items()):
        binding = image_to_memory.get(img_id)
        if binding:
            ic = initial_contents.get(binding.memory_id)
            if ic:
                extractable.append((img, binding, ic))
    
    print(f"\nFound {len(extractable)} extractable textures out of {len(images)} total\n")
    
    # 按尺寸排序
    extractable.sort(key=lambda x: x[0].width * x[0].height, reverse=True)
    
    print(f"{'ID':>8} | {'Size':>15} | {'Format':>35} | {'Buffer':>8} | {'Offset':>12}")
    print("-" * 90)
    
    for img, binding, ic in extractable[:50]:  # 只显示前50个
        size_str = f"{img.width}x{img.height}x{img.depth}"
        print(f"{img.resource_id:>8} | {size_str:>15} | {img.format:>35} | {ic.buffer_index:>8} | {binding.offset:>12}")
    
    if len(extractable) > 50:
        print(f"\n... and {len(extractable) - 50} more textures")


def extract_texture(image_id: int,
                    images: Dict[int, ImageInfo],
                    bindings: List[MemoryBinding],
                    initial_contents: Dict[int, InitialContents],
                    zip_path: Path,
                    output_dir: Path,
                    decode: bool = False):
    """提取指定纹理的原始数据，可选解码为 PNG"""
    
    if image_id not in images:
        print(f"[ERROR] Image {image_id} not found")
        return
    
    img = images[image_id]
    
    # 查找绑定
    binding = None
    for b in bindings:
        if b.image_id == image_id:
            binding = b
            break
    
    if not binding:
        print(f"[ERROR] No memory binding found for image {image_id}")
        return
    
    # 查找初始内容
    ic = initial_contents.get(binding.memory_id)
    if not ic:
        print(f"[ERROR] No initial contents for memory {binding.memory_id}")
        return
    
    print(f"\n[*] Extracting texture {image_id}")
    print(f"    Size: {img.width}x{img.height}x{img.depth}")
    print(f"    Format: {img.format}")
    print(f"    Memory: {binding.memory_id} @ offset {binding.offset}")
    print(f"    Buffer index: {ic.buffer_index}")
    
    # 从 ZIP 提取
    buffer_name = f"{ic.buffer_index:06d}"
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        try:
            data = zf.read(buffer_name)
            print(f"    Buffer size: {len(data)} bytes")
            
            # 计算纹理大小（简化版，不处理压缩格式）
            # TODO: 根据 format 计算实际字节大小
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 提取纹理数据（从 offset 开始）
            texture_data = data[binding.offset:] if binding.offset > 0 else data
            
            # 输出原始内存数据
            raw_path = output_dir / f"texture_{image_id}_{img.width}x{img.height}.bin"
            with open(raw_path, 'wb') as f:
                f.write(texture_data)
            print(f"    Saved raw: {raw_path}")
            
            # 如果启用解码且解码器可用
            if decode and DECODER_AVAILABLE:
                try:
                    print(f"    Decoding {img.format}...")
                    rgba_data = decode_texture(
                        texture_data, 
                        img.width, 
                        img.height, 
                        img.format
                    )
                    
                    # 保存为 PNG
                    png_path = output_dir / f"texture_{image_id}_{img.width}x{img.height}.png"
                    save_as_png(rgba_data, img.width, img.height, str(png_path))
                    print(f"    ✓ Decoded to PNG: {png_path}")
                    
                except TextureDecodeError as e:
                    print(f"    [WARN] Decode failed: {e}")
                    print(f"           Supported formats: {get_supported_formats()}")
                except Exception as e:
                    print(f"    [ERROR] Unexpected decode error: {e}")
            
        except KeyError:
            print(f"[ERROR] Buffer {buffer_name} not found in ZIP")


def main():
    parser = argparse.ArgumentParser(description='Extract textures from RenderDoc ZIP+XML export')
    parser.add_argument('xml_file', help='Path to the .xml file')
    parser.add_argument('--list-textures', '-l', action='store_true', help='List all extractable textures')
    parser.add_argument('--extract', '-e', type=int, help='Extract texture by image ID')
    parser.add_argument('--decode', '-d', action='store_true', help='Decode texture to PNG (requires BC decoder)')
    parser.add_argument('--output', '-o', default='./extracted_textures', help='Output directory')
    
    args = parser.parse_args()
    
    # 检查解码器可用性
    if args.decode and not DECODER_AVAILABLE:
        print("[WARNING] Decoder module not available. Install PIL or run from scripts/rdc_analyzer/")
        print("          Falling back to raw extraction only.")
    
    xml_path = Path(args.xml_file)
    if not xml_path.exists():
        print(f"[ERROR] XML file not found: {xml_path}")
        sys.exit(1)
    
    # 推断 ZIP 路径 - 尝试多种命名约定
    # 1. 去掉 .xml 后缀（如 capture.xml -> capture）
    # 2. 替换为 .zip 后缀（如 capture.xml -> capture.zip）
    zip_candidates = [
        xml_path.parent / xml_path.name.replace('.xml', ''),  # capture.xml -> capture
        xml_path.with_suffix('.zip'),                          # capture.xml -> capture.zip
        xml_path.with_suffix(''),                              # backup: 无后缀
    ]
    zip_path = None
    for candidate in zip_candidates:
        if candidate.exists():
            zip_path = candidate
            break
    if zip_path is None:
        zip_path = zip_candidates[0]  # 默认第一个用于报错信息
    
    print(f"[*] XML: {xml_path}")
    print(f"[*] ZIP: {zip_path} {'(exists)' if zip_path.exists() else '(NOT FOUND)'}")
    
    # 解析 XML
    images, bindings, initial_contents = parse_xml_regex(xml_path)
    
    if args.list_textures:
        list_textures(images, bindings, initial_contents)
    elif args.extract:
        if not zip_path.exists():
            print(f"[ERROR] ZIP file required for extraction: {zip_path}")
            sys.exit(1)
        extract_texture(args.extract, images, bindings, initial_contents, 
                       zip_path, Path(args.output), decode=args.decode)
    else:
        print("\nUse --list-textures to see all textures")
        print("Use --extract <id> to extract a specific texture")


if __name__ == '__main__':
    main()