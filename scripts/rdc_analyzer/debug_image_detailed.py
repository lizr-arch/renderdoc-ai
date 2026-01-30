#!/usr/bin/env python3
"""详细分析 vkCreateImage chunk 的字节结构，找出正确的字段偏移"""

import struct
import sys
sys.path.insert(0, r'd:\Code\git\renderdoc\scripts\rdc_analyzer')

from rdc_parser import RDCParser

# VkFormat 名称映射 (常见格式)
VK_FORMAT_NAMES = {
    0: "UNDEFINED",
    37: "R8G8B8A8_UNORM",
    43: "R8G8B8A8_SRGB",
    44: "B8G8R8A8_UNORM",
    50: "B8G8R8A8_SRGB",
    64: "A2B10G10R10_UNORM_PACK32",
    97: "R32_SFLOAT",
    98: "R32G32_SFLOAT",
    100: "R32G32B32A32_SFLOAT",
    103: "R16G16_SFLOAT",
    109: "R16G16B16A16_SFLOAT",
    122: "D16_UNORM",
    124: "D32_SFLOAT",
    126: "D24_UNORM_S8_UINT",
    127: "D32_SFLOAT_S8_UINT",
    129: "BC1_RGB_UNORM_BLOCK",
    147: "ASTC_4x4_UNORM_BLOCK",
    148: "ASTC_4x4_SRGB_BLOCK",
    157: "ASTC_8x8_UNORM_BLOCK",
}

def format_name(fmt: int) -> str:
    return VK_FORMAT_NAMES.get(fmt, f"FORMAT_{fmt}")

def analyze_chunk_detailed(data: bytes, chunk_offset: int, chunk_length: int):
    """逐字节分析 chunk 数据"""
    print(f"\n{'='*70}")
    print(f"Chunk at offset {chunk_offset}, length={chunk_length}")
    print(f"{'='*70}")
    
    # 提取 chunk 数据
    chunk_data = data[chunk_offset:chunk_offset + chunk_length]
    
    # 打印完整 hex dump
    print("\nComplete HEX dump:")
    for i in range(0, min(len(chunk_data), 128), 16):
        hex_str = ' '.join(f'{b:02x}' for b in chunk_data[i:i+16])
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk_data[i:i+16])
        print(f"  {i:04x}: {hex_str:<48} {ascii_str}")
    
    # 解析关键字段
    print("\nField-by-field analysis:")
    
    # Device ResourceId (8 bytes at offset 0)
    device_id = struct.unpack_from('<Q', chunk_data, 0)[0]
    print(f"  [0x00-0x07] Device ResourceId = {device_id:#x} ({device_id})")
    
    # 接下来的 4 字节 - 标记或 sType?
    marker = struct.unpack_from('<I', chunk_data, 8)[0]
    print(f"  [0x08-0x0B] Marker/Tag = {marker} ({marker:#x})")
    
    # 尝试不同的解释方式
    print("\n  --- Interpretation A: Standard VkImageCreateInfo (offset 12) ---")
    try:
        # 从 offset 12 (0x0C) 开始读
        # VkImageCreateInfo 不包含 sType/pNext 在序列化数据中
        # 直接是 flags
        offset = 12
        flags = struct.unpack_from('<I', chunk_data, offset)[0]
        print(f"    [0x0C] flags = {flags:#x}")
        
        # imageType (offset 16)
        image_type = struct.unpack_from('<I', chunk_data, offset + 4)[0]
        print(f"    [0x10] imageType = {image_type} (0=1D, 1=2D, 2=3D)")
        
        # format (offset 20)
        fmt = struct.unpack_from('<I', chunk_data, offset + 8)[0]
        print(f"    [0x14] format = {fmt} ({format_name(fmt)})")
        
        # extent.width (offset 24)
        width = struct.unpack_from('<I', chunk_data, offset + 12)[0]
        print(f"    [0x18] extent.width = {width}")
        
        # extent.height (offset 28)
        height = struct.unpack_from('<I', chunk_data, offset + 16)[0]
        print(f"    [0x1C] extent.height = {height}")
        
        # extent.depth (offset 32)
        depth = struct.unpack_from('<I', chunk_data, offset + 20)[0]
        print(f"    [0x20] extent.depth = {depth}")
        
        # mipLevels (offset 36)
        mip_levels = struct.unpack_from('<I', chunk_data, offset + 24)[0]
        print(f"    [0x24] mipLevels = {mip_levels}")
        
        # arrayLayers (offset 40)
        array_layers = struct.unpack_from('<I', chunk_data, offset + 28)[0]
        print(f"    [0x28] arrayLayers = {array_layers}")
        
        # samples (offset 44)
        samples = struct.unpack_from('<I', chunk_data, offset + 32)[0]
        print(f"    [0x2C] samples = {samples}")
        
        # tiling (offset 48)
        tiling = struct.unpack_from('<I', chunk_data, offset + 36)[0]
        print(f"    [0x30] tiling = {tiling} (0=OPTIMAL, 1=LINEAR)")
        
        # usage (offset 52)
        usage = struct.unpack_from('<I', chunk_data, offset + 40)[0]
        print(f"    [0x34] usage = {usage:#x}")
        
        # 验证是否合理
        is_valid = (
            image_type <= 2 and
            0 < fmt < 300 and
            0 < width <= 16384 and
            0 < height <= 16384 and
            0 < depth <= 2048 and
            0 < mip_levels <= 15 and
            0 < array_layers <= 2048 and
            samples in (1, 2, 4, 8, 16, 32, 64) and
            tiling <= 1 and
            0 < usage < 0xFFFF
        )
        print(f"    Valid: {is_valid}")
        
    except struct.error as e:
        print(f"    Error: {e}")
    
    print("\n  --- Interpretation B: With 1-byte padding after flags (offset 17) ---")
    try:
        # 可能有 1 字节填充
        offset = 12
        flags = struct.unpack_from('<I', chunk_data, offset)[0]
        print(f"    [0x0C] flags = {flags:#x}")
        
        # 跳过 1 字节 padding
        base = 17
        
        image_type = struct.unpack_from('<I', chunk_data, base)[0]
        print(f"    [0x11] imageType = {image_type}")
        
        fmt = struct.unpack_from('<I', chunk_data, base + 4)[0]
        print(f"    [0x15] format = {fmt} ({format_name(fmt)})")
        
        width = struct.unpack_from('<I', chunk_data, base + 8)[0]
        print(f"    [0x19] extent.width = {width}")
        
        height = struct.unpack_from('<I', chunk_data, base + 12)[0]
        print(f"    [0x1D] extent.height = {height}")
        
        depth = struct.unpack_from('<I', chunk_data, base + 16)[0]
        print(f"    [0x21] extent.depth = {depth}")
        
        mip_levels = struct.unpack_from('<I', chunk_data, base + 20)[0]
        print(f"    [0x25] mipLevels = {mip_levels}")
        
        array_layers = struct.unpack_from('<I', chunk_data, base + 24)[0]
        print(f"    [0x29] arrayLayers = {array_layers}")
        
        samples = struct.unpack_from('<I', chunk_data, base + 28)[0]
        print(f"    [0x2D] samples = {samples}")
        
        tiling = struct.unpack_from('<I', chunk_data, base + 32)[0]
        print(f"    [0x31] tiling = {tiling}")
        
        usage = struct.unpack_from('<I', chunk_data, base + 36)[0]
        print(f"    [0x35] usage = {usage:#x}")
        
        is_valid = (
            image_type <= 2 and
            0 < fmt < 300 and
            0 < width <= 16384 and
            0 < height <= 16384 and
            0 < depth <= 2048 and
            0 < mip_levels <= 15 and
            0 < array_layers <= 2048 and
            samples in (1, 2, 4, 8, 16, 32, 64) and
            tiling <= 1 and
            0 < usage < 0xFFFF
        )
        print(f"    Valid: {is_valid}")
        
    except struct.error as e:
        print(f"    Error: {e}")
    
    # 尝试所有可能的 4 字节对齐偏移来找 format 37 或其他已知格式
    print("\n  --- Scanning for known VkFormat values (4-byte aligned) ---")
    known_formats = [37, 43, 44, 50, 64, 97, 98, 100, 109, 122, 124, 126, 127, 129, 147, 148, 157, 171]
    for i in range(0, min(len(chunk_data) - 4, 100), 4):
        val = struct.unpack_from('<I', chunk_data, i)[0]
        if val in known_formats:
            # 检查前后是否像 width/height
            prev_val = struct.unpack_from('<I', chunk_data, i - 4)[0] if i >= 4 else 0
            next_val = struct.unpack_from('<I', chunk_data, i + 4)[0] if i + 4 < len(chunk_data) else 0
            next_val2 = struct.unpack_from('<I', chunk_data, i + 8)[0] if i + 8 < len(chunk_data) else 0
            
            print(f"    Found format={val} ({format_name(val)}) at offset 0x{i:02x}")
            print(f"      prev[0x{i-4:02x}]={prev_val} (imageType?), next[0x{i+4:02x}]={next_val} (width?), next2[0x{i+8:02x}]={next_val2} (height?)")
    
    # 对于长格式，扫描所有可能是 (width, height) 对的值
    if chunk_length == 136:
        print("\n  --- Scanning for plausible (width, height) pairs in long format ---")
        for i in range(16, min(len(chunk_data) - 8, 80), 4):
            w = struct.unpack_from('<I', chunk_data, i)[0]
            h = struct.unpack_from('<I', chunk_data, i + 4)[0]
            # 检查是否看起来像尺寸
            if 1 <= w <= 8192 and 1 <= h <= 8192 and w * h >= 16:
                # 检查前面是否有合理的 format
                if i >= 4:
                    prev = struct.unpack_from('<I', chunk_data, i - 4)[0]
                    if 1 <= prev <= 200:  # VkFormat 范围
                        print(f"    Possible: format={prev} at 0x{i-4:02x}, width={w} at 0x{i:02x}, height={h} at 0x{i+4:02x}")
        
        # 尝试特定的长格式解析 (基于观察到的模式)
        print("\n  --- Long format interpretation (pNext extended) ---")
        try:
            # 长格式看起来有这个模式:
            # 0x00-0x07: Device ResourceId
            # 0x08-0x0B: Marker (14)
            # 0x0C-0x0F: flags_high? (0x01)
            # 0x10-0x17: 某种指针或扩展ID
            # 0x18-0x1F: 某种指针或扩展ID  
            # 0x20: 单字节 0x00
            # 0x21-0x24: imageType (offset from here = 0x21)
            # 0x25-0x28: format
            # 0x29-0x2C: ...
            
            # 让我尝试从 0x40 开始，因为那里看起来像是 VkImageCreateInfo 后半部分
            # 实际上观察 hex dump:
            # 0x24: format (44 = B8G8R8A8_UNORM)
            # 0x28: another_format (50 = B8G8R8A8_SRGB)
            # 0x34: width (1024 in chunk#3)
            # 0x38: height (1024 in chunk#3)
            
            # 直接按字节顺序读取关键位置
            # 基于 hex dump 分析:
            # 0x20: 可能是某种标记或 imageType
            # 0x24: format
            # 0x28: format2 (viewFormat?)
            # 0x2C: 小尺寸 (8)
            # 0x30: 1 (arrayLayers?)
            # 0x34: format again (50)
            # 0x38: width (大尺寸如 1024)
            # 0x3C: height (大尺寸如 1024)
            
            print("\n    Reading specific offsets in long format:")
            val_20 = struct.unpack_from('<I', chunk_data, 0x20)[0]
            val_24 = struct.unpack_from('<I', chunk_data, 0x24)[0]
            val_28 = struct.unpack_from('<I', chunk_data, 0x28)[0]
            val_2C = struct.unpack_from('<I', chunk_data, 0x2C)[0]
            val_30 = struct.unpack_from('<I', chunk_data, 0x30)[0]
            val_34 = struct.unpack_from('<I', chunk_data, 0x34)[0]
            val_38 = struct.unpack_from('<I', chunk_data, 0x38)[0]
            val_3C = struct.unpack_from('<I', chunk_data, 0x3C)[0]
            
            print(f"      0x20={val_20}, 0x24={val_24} ({format_name(val_24)}), 0x28={val_28} ({format_name(val_28)})")
            print(f"      0x2C={val_2C}, 0x30={val_30}, 0x34={val_34} ({format_name(val_34)})")
            print(f"      0x38={val_38} (width?), 0x3C={val_3C} (height?)")
            
            # 如果 0x24 是有效的 format，并且 0x38/0x3C 是合理的尺寸
            if 1 <= val_24 <= 200 and 1 <= val_38 <= 16384 and 1 <= val_3C <= 16384:
                print(f"\n    ** VALID Long Format: format={val_24} ({format_name(val_24)}), {val_38}x{val_3C} **")
            
        except struct.error as e:
            print(f"    Error: {e}")

def main():
    rdc_path = r"D:\renderdoc\goog pixel-9\g145.rdc"
    
    print(f"Loading RDC: {rdc_path}")
    
    try:
        with RDCParser(rdc_path) as parser:
            # 解析文件头
            rdc_info = parser.parse_header()
            print(f"RDC Version: {rdc_info.header.version}")
            print(f"Sections: {len(rdc_info.sections)}")
            
            # 获取 frame capture 数据
            frame_data = parser.get_frame_capture_data()
            print(f"Frame capture data: {len(frame_data)} bytes")
            
            # 解析 chunks
            chunks = parser.parse_chunks(frame_data)
            print(f"Total chunks: {len(chunks)}")
            
            # 找到 vkCreateImage chunks (ID 1015)
            image_chunks = [c for c in chunks if c.chunk_id == 1015]
            print(f"\nFound {len(image_chunks)} vkCreateImage chunks")
            
            # 分析前 5 个不同长度的 chunk
            analyzed_lengths = set()
            count = 0
            for chunk in image_chunks:
                if chunk.length not in analyzed_lengths and count < 5:
                    analyze_chunk_detailed(frame_data, chunk.data_offset, chunk.length)
                    analyzed_lengths.add(chunk.length)
                    count += 1
            
            # 额外分析几个长格式 (136 bytes) 的 chunk 来找规律
            print("\n\n========== EXTRA: More 136-byte chunks ==========")
            long_chunks = [c for c in image_chunks if c.length == 136][:3]
            for i, chunk in enumerate(long_chunks):
                print(f"\n--- Long chunk #{i+1} ---")
                analyze_chunk_detailed(frame_data, chunk.data_offset, chunk.length)
            
            # 统计不同长度
            length_counts = {}
            for chunk in image_chunks:
                length_counts[chunk.length] = length_counts.get(chunk.length, 0) + 1
            
            print(f"\n\nChunk length distribution:")
            for length, cnt in sorted(length_counts.items()):
                print(f"  Length {length}: {cnt} chunks")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
