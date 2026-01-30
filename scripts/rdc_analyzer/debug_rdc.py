#!/usr/bin/env python3
"""调试脚本：分析 RDC 文件的 FrameCapture 数据"""

import struct
import sys
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from rdc_parser import RDCParser, SPIRV_MAGIC, FIRST_DRIVER_CHUNK

def debug_rdc(filepath: str):
    """调试 RDC 文件"""
    print(f"=== Debugging RDC: {filepath} ===\n")
    
    with RDCParser(filepath) as parser:
        info = parser.parse_header()
        print(f"Driver: {info.metadata.driver_name} (ID: {info.metadata.driver_id})")
        
        # 获取 FrameCapture 数据
        print("\n=== Reading FrameCapture ===")
        fc_data = parser.get_frame_capture_data()
        print(f"Decompressed size: {len(fc_data)} bytes ({len(fc_data) / 1024 / 1024:.2f} MB)")
        
        # 打印前 256 字节（十六进制）
        print("\n=== First 256 bytes (hex) ===")
        for i in range(0, min(256, len(fc_data)), 16):
            hex_str = ' '.join(f'{b:02x}' for b in fc_data[i:i+16])
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in fc_data[i:i+16])
            print(f"{i:08x}: {hex_str:<48} {ascii_str}")
        
        # 搜索 SPIR-V magic
        print("\n=== Searching for SPIR-V magic (0x07230203) ===")
        spirv_magic_bytes = struct.pack('<I', SPIRV_MAGIC)
        
        count = 0
        pos = 0
        spirv_offsets = []
        while True:
            idx = fc_data.find(spirv_magic_bytes, pos)
            if idx < 0:
                break
            spirv_offsets.append(idx)
            count += 1
            if count <= 10:
                # 打印周围数据
                context_start = max(0, idx - 32)
                context = fc_data[context_start:idx + 64]
                print(f"  Found at offset 0x{idx:08x} ({idx}):")
                for j in range(0, len(context), 16):
                    hex_str = ' '.join(f'{b:02x}' for b in context[j:j+16])
                    print(f"    {context_start + j:08x}: {hex_str}")
            pos = idx + 4
        
        print(f"\nTotal SPIR-V magic occurrences: {count}")
        if count > 10:
            print(f"  (Showing first 10 only)")
        
        # 手动解析第一个 Chunk 
        print("\n=== Manual Chunk Parsing (first 5) ===")
        offset = 0
        for i in range(5):
            if offset + 4 > len(fc_data):
                break
            
            c = struct.unpack_from('<I', fc_data, offset)[0]
            print(f"\nChunk {i} at offset {offset}:")
            print(f"  Raw header: 0x{c:08x}")
            print(f"  Chunk ID: {c & 0xFFFF}")
            print(f"  Flags: 0x{(c >> 16):04x}")
            
            flags = c & ~0xFFFF
            header_offset = offset + 4
            
            if flags & 0x00010000:  # CALLSTACK
                num_frames = struct.unpack_from('<I', fc_data, header_offset)[0]
                print(f"  Callstack: {num_frames} frames")
                header_offset += 4 + num_frames * 8
            
            if flags & 0x00020000:  # THREAD_ID
                tid = struct.unpack_from('<Q', fc_data, header_offset)[0]
                print(f"  ThreadID: {tid}")
                header_offset += 8
            
            if flags & 0x00040000:  # DURATION
                dur = struct.unpack_from('<q', fc_data, header_offset)[0]
                print(f"  Duration: {dur}")
                header_offset += 8
            
            if flags & 0x00080000:  # TIMESTAMP
                ts = struct.unpack_from('<Q', fc_data, header_offset)[0]
                print(f"  Timestamp: {ts}")
                header_offset += 8
            
            if flags & 0x00100000:  # 64BIT_SIZE
                length = struct.unpack_from('<Q', fc_data, header_offset)[0]
                print(f"  Length (64-bit): {length}")
                header_offset += 8
            else:
                length = struct.unpack_from('<I', fc_data, header_offset)[0]
                print(f"  Length (32-bit): {length}")
                header_offset += 4
            
            print(f"  Data starts at: {header_offset}")
            
            # 显示数据开头
            data_preview = fc_data[header_offset:header_offset + 32]
            hex_str = ' '.join(f'{b:02x}' for b in data_preview)
            print(f"  Data preview: {hex_str}")
            
            # 移动到下一个 chunk
            offset = header_offset + length
        
        # 解析 Chunks
        print("\n=== Parsing Chunks (using parser) ===")
        chunks = parser.parse_chunks(fc_data)
        print(f"Total chunks: {len(chunks)}")
        
        # 统计各类型
        chunk_counts = {}
        shader_chunks = []
        for chunk in chunks:
            name = chunk.chunk_name
            chunk_counts[name] = chunk_counts.get(name, 0) + 1
            if chunk.chunk_id == 1019:  # vkCreateShaderModule
                shader_chunks.append(chunk)
        
        print("\nChunk type distribution:")
        for name, cnt in sorted(chunk_counts.items(), key=lambda x: -x[1])[:20]:
            print(f"  {name}: {cnt}")
        
        print(f"\nvkCreateShaderModule chunks: {len(shader_chunks)}")
        
        # 详细检查 shader chunks
        if shader_chunks:
            print("\n=== Shader Chunk Details ===")
            for i, chunk in enumerate(shader_chunks[:5]):
                print(f"\n[{i}] Chunk at offset {chunk.data_offset}, length {chunk.length}")
                chunk_data = fc_data[chunk.data_offset:chunk.data_offset + min(256, chunk.length)]
                for j in range(0, len(chunk_data), 16):
                    hex_str = ' '.join(f'{b:02x}' for b in chunk_data[j:j+16])
                    print(f"  {j:04x}: {hex_str}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python debug_rdc.py <rdc_file>")
        sys.exit(1)
    
    debug_rdc(sys.argv[1])
