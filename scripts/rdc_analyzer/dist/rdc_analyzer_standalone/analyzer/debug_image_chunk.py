#!/usr/bin/env python3
"""
详细分析 vkCreateImage chunk 的数据结构
"""

import sys
import os
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rdc_parser import RDCParser, VK_FORMAT_NAMES


def analyze_chunk_structure(data: bytes, offset: int, length: int):
    """分析单个 chunk 的数据结构"""
    end = offset + length
    
    print(f"\n详细字段分析 (offset={offset}, length={length}):")
    print("-" * 60)
    
    # 按不同方式解释数据
    pos = offset
    
    # 1. Device ResourceId (8 bytes)
    device_id = struct.unpack_from('<Q', data, pos)[0]
    print(f"  [0x00] Device ResourceId: {device_id} (0x{device_id:x})")
    pos += 8
    
    # 2. 接下来的数据可能是 VkImageCreateInfo 的序列化
    # RenderDoc 的 Serialiser 会跳过 sType/pNext，直接序列化字段
    
    # 尝试读取 VkImageCreateInfo 字段
    # 字段顺序 (基于 VkImageCreateInfo 定义):
    # - sType (int32, 但 RenderDoc 可能跳过)
    # - pNext (pointer, RenderDoc 可能跳过)
    # - flags (VkImageCreateFlags, uint32)
    # - imageType (VkImageType, uint32)
    # - format (VkFormat, uint32)
    # - extent.width (uint32)
    # - extent.height (uint32)
    # - extent.depth (uint32)
    # - mipLevels (uint32)
    # - arrayLayers (uint32)
    # - samples (VkSampleCountFlagBits, uint32)
    # - tiling (VkImageTiling, uint32)
    # - usage (VkImageUsageFlags, uint32)
    
    remaining = data[pos:end]
    print(f"\n  剩余数据 ({len(remaining)} bytes), 按 uint32 解释:")
    
    for i in range(0, min(len(remaining) - 3, 60), 4):
        val = struct.unpack_from('<I', remaining, i)[0]
        
        # 尝试解释这个值
        interpretation = ""
        
        # 检查是否像 imageType
        if val <= 2:
            type_names = {0: "1D", 1: "2D", 2: "3D"}
            interpretation += f" [可能是 imageType: {type_names.get(val, '?')}]"
        
        # 检查是否像 format
        if val in VK_FORMAT_NAMES:
            interpretation += f" [可能是 format: {VK_FORMAT_NAMES[val]}]"
        
        # 检查是否像尺寸 (2的幂次)
        if val > 0 and val <= 16384 and (val & (val - 1)) == 0:
            interpretation += f" [可能是尺寸: {val}]"
        elif 1 <= val <= 4096:
            interpretation += f" [可能是尺寸: {val}]"
        
        # 检查是否像 samples
        if val in (1, 2, 4, 8, 16, 32, 64):
            interpretation += f" [可能是 samples: {val}x]"
        
        # 检查是否像 usage flags
        if 0 < val < 0x200:
            flags = []
            if val & 0x01: flags.append("TRANSFER_SRC")
            if val & 0x02: flags.append("TRANSFER_DST")
            if val & 0x04: flags.append("SAMPLED")
            if val & 0x08: flags.append("STORAGE")
            if val & 0x10: flags.append("COLOR_ATTACHMENT")
            if val & 0x20: flags.append("DEPTH_STENCIL")
            if flags:
                interpretation += f" [可能是 usage: {','.join(flags)}]"
        
        print(f"    [{i:3d}] 0x{pos+i:04x}: {val:10d} (0x{val:08x}){interpretation}")
    
    # 读取为 uint64
    print(f"\n  按 uint64 解释:")
    for i in range(0, min(len(remaining) - 7, 48), 8):
        val = struct.unpack_from('<Q', remaining, i)[0]
        interpretation = ""
        if 0 < val < (1 << 48):
            interpretation = " [可能是 ResourceId]"
        print(f"    [{i:3d}] 0x{pos+i:04x}: {val} (0x{val:x}){interpretation}")


def main():
    if len(sys.argv) < 2:
        print("Usage: py -3 debug_image_chunk.py <rdc_file>")
        sys.exit(1)
    
    rdc_path = sys.argv[1]
    
    with RDCParser(rdc_path) as parser:
        parser.parse_header()
        fc_data = parser.get_frame_capture_data()
        chunks = parser.parse_chunks(fc_data)
        
        # 找到 vkCreateImage chunks
        create_image_chunks = [c for c in chunks if c.chunk_name == 'vkCreateImage']
        print(f"找到 {len(create_image_chunks)} 个 vkCreateImage chunks")
        
        # 分析前几个
        for i, chunk in enumerate(create_image_chunks[:8]):
            print(f"\n{'='*70}")
            print(f"Chunk {i}: chunk_id={chunk.chunk_id}, offset={chunk.data_offset}, length={chunk.length}")
            print(f"{'='*70}")
            
            # Hex dump
            chunk_data = fc_data[chunk.data_offset:chunk.data_offset + min(128, chunk.length)]
            print("\nHex Dump:")
            for j in range(0, len(chunk_data), 16):
                hex_part = ' '.join(f'{b:02x}' for b in chunk_data[j:j+16])
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk_data[j:j+16])
                print(f"  {j:04x}: {hex_part:<48} {ascii_part}")
            
            analyze_chunk_structure(fc_data, chunk.data_offset, chunk.length)


if __name__ == '__main__':
    main()
