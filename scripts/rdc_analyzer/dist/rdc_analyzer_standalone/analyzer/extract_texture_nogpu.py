#!/usr/bin/env python3
"""
无 GPU 纹理数据提取原型 (No-GPU Texture Extraction Prototype)

目标: 验证从 RDC 文件中提取纹理数据而不需要 GPU 回放的可行性。

原理:
1. 使用 CaptureFile.GetStructuredData() 获取 SDFile
2. SDFile.chunks 包含所有序列化的 chunk，包括 InitialContents
3. SDFile.buffers 包含原始二进制数据（纹理像素）
4. 通过 chunk 中的 buffer 索引可以定位到纹理数据

关键发现（来自源码分析）：
- renderdoc/serialise/serialiser.h:369-376:
  在 ExportStructure 模式下，SERIALISE_ELEMENT_ARRAY 会：
  1. 将 buffer 索引存入 SDObject.data.basic.u
  2. 将实际数据存入 SDFile.buffers 列表

用法:
    python extract_texture_nogpu.py <rdc_file> [--output-dir <dir>]
"""

import sys
import os
import argparse
import json
from pathlib import Path

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
except ImportError:
    print("Error: renderdoc module not found.")
    print("This script must be run from within RenderDoc's Python environment")
    print("or with PYTHONPATH set to include the renderdoc module.")
    sys.exit(1)


def find_initial_contents_chunks(sd_file):
    """
    在 SDFile 中查找 InitialContents 类型的 chunk。
    
    InitialContents chunk 存储资源的初始状态，包括纹理像素数据。
    """
    initial_contents = []
    
    for i, chunk in enumerate(sd_file.chunks):
        chunk_name = chunk.name if hasattr(chunk, 'name') else str(chunk)
        
        # InitialContents chunk 的名称通常包含 "InitialContents" 或 ID
        # 可能的命名: "InitialContents", "Resource X InitialContents" 等
        if 'InitialContents' in chunk_name or 'Initial' in chunk_name:
            initial_contents.append({
                'index': i,
                'name': chunk_name,
                'chunk': chunk
            })
    
    return initial_contents


def analyze_chunk_structure(chunk, depth=0, max_depth=5):
    """
    递归分析 chunk 的结构，找到关联的 buffer 索引。
    """
    indent = "  " * depth
    result = {}
    
    if depth > max_depth:
        return {"_truncated": True}
    
    # 基本属性
    if hasattr(chunk, 'name'):
        result['name'] = chunk.name
    
    if hasattr(chunk, 'type'):
        type_obj = chunk.type
        if hasattr(type_obj, 'basetype'):
            result['basetype'] = str(type_obj.basetype)
        if hasattr(type_obj, 'name'):
            result['typename'] = type_obj.name
    
    # 数据值
    if hasattr(chunk, 'data'):
        data = chunk.data
        if hasattr(data, 'basic'):
            basic = data.basic
            # SDObjectPODData 联合体 - 包含 u, i, d, b, c, id
            if hasattr(basic, 'u'):
                result['value_u'] = basic.u  # 可能是 buffer 索引！
            if hasattr(basic, 'i'):
                result['value_i'] = basic.i
        if hasattr(data, 'str') and data.str:
            result['value_str'] = str(data.str)
    
    # 子节点
    if hasattr(chunk, 'NumChildren') and chunk.NumChildren() > 0:
        children = []
        for i in range(min(chunk.NumChildren(), 50)):  # 限制子节点数量
            child = chunk.GetChild(i)
            child_info = analyze_chunk_structure(child, depth + 1, max_depth)
            children.append(child_info)
        result['children'] = children
        if chunk.NumChildren() > 50:
            result['children_truncated'] = True
            result['total_children'] = chunk.NumChildren()
    
    return result


def find_texture_related_chunks(sd_file):
    """
    查找与纹理相关的 chunk。
    
    纹理相关 chunk 可能的名称:
    - CreateTexture1D/2D/3D
    - InitialContents (包含像素数据)
    - Texture 相关的资源描述
    """
    texture_chunks = []
    
    texture_keywords = [
        'Texture', 'Tex2D', 'Tex1D', 'Tex3D', 'TexCube',
        'SRV', 'RTV', 'DSV', 'UAV',  # Views
        'InitialContents', 'Initial'
    ]
    
    for i, chunk in enumerate(sd_file.chunks):
        chunk_name = chunk.name if hasattr(chunk, 'name') else ''
        
        for keyword in texture_keywords:
            if keyword.lower() in chunk_name.lower():
                texture_chunks.append({
                    'index': i,
                    'name': chunk_name,
                    'chunk': chunk
                })
                break
    
    return texture_chunks


def extract_buffers_info(sd_file):
    """
    提取 SDFile 中所有 buffer 的信息。
    """
    buffers_info = []
    
    for i, buf in enumerate(sd_file.buffers):
        size = len(buf) if buf else 0
        
        # 尝试识别数据类型
        data_type = "unknown"
        preview = ""
        
        if size > 0:
            # 检查前几个字节
            header = bytes(buf[:min(16, size)])
            
            # 常见文件头检测
            if header[:4] == b'\x89PNG':
                data_type = "PNG image"
            elif header[:2] == b'\xff\xd8':
                data_type = "JPEG image"
            elif header[:4] == b'DDS ':
                data_type = "DDS texture"
            elif header[:4] == b'RIFF':
                data_type = "RIFF container"
            else:
                data_type = "raw binary"
                preview = header.hex()
        
        buffers_info.append({
            'index': i,
            'size': size,
            'type': data_type,
            'preview': preview[:32] if preview else ""
        })
    
    return buffers_info


def dump_buffer_to_file(sd_file, buffer_index, output_path):
    """
    将指定 buffer 导出到文件。
    """
    if buffer_index < 0 or buffer_index >= len(sd_file.buffers):
        print(f"Error: Buffer index {buffer_index} out of range (0-{len(sd_file.buffers)-1})")
        return False
    
    buf = sd_file.buffers[buffer_index]
    if not buf or len(buf) == 0:
        print(f"Error: Buffer {buffer_index} is empty")
        return False
    
    with open(output_path, 'wb') as f:
        f.write(bytes(buf))
    
    print(f"Dumped buffer {buffer_index} ({len(buf)} bytes) to {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='No-GPU Texture Extraction Prototype',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('rdc_file', help='Path to the RDC capture file')
    parser.add_argument('--output-dir', '-o', default='.', 
                        help='Output directory for extracted data')
    parser.add_argument('--dump-buffers', action='store_true',
                        help='Dump all buffers to files')
    parser.add_argument('--analyze-chunks', action='store_true',
                        help='Analyze texture-related chunks structure')
    parser.add_argument('--json-output', '-j', 
                        help='Output analysis to JSON file')
    
    args = parser.parse_args()
    
    rdc_path = Path(args.rdc_file)
    if not rdc_path.exists():
        print(f"Error: File not found: {rdc_path}")
        return 1
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=== No-GPU Texture Extraction Prototype ===")
    print(f"Input: {rdc_path}")
    print(f"Output: {output_dir}")
    print()
    
    # 初始化 RenderDoc
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    
    try:
        # 打开 capture 文件
        cap = rd.OpenCaptureFile()
        result = cap.OpenFile(str(rdc_path), '', None)
        
        if result != rd.ResultCode.Succeeded:
            print(f"Error: Failed to open file: {result}")
            return 1
        
        print(f"File opened successfully")
        print(f"Driver: {cap.DriverName()}")
        print(f"Machine Ident: {cap.MachineIdent()}")
        print()
        
        # === 关键步骤：获取 StructuredData 而不需要 GPU ===
        print("Getting structured data (no GPU required)...")
        sd_file = cap.GetStructuredData()
        
        print(f"Chunks: {len(sd_file.chunks)}")
        print(f"Buffers: {len(sd_file.buffers)}")
        print()
        
        # 分析结果收集
        analysis = {
            'file': str(rdc_path),
            'driver': cap.DriverName(),
            'chunks_count': len(sd_file.chunks),
            'buffers_count': len(sd_file.buffers),
        }
        
        # 分析 buffers
        print("=== Buffer Analysis ===")
        buffers_info = extract_buffers_info(sd_file)
        analysis['buffers'] = buffers_info
        
        # 显示前 20 个 buffer
        for buf_info in buffers_info[:20]:
            print(f"  Buffer {buf_info['index']}: {buf_info['size']} bytes, "
                  f"type={buf_info['type']}, preview={buf_info['preview']}")
        
        if len(buffers_info) > 20:
            print(f"  ... and {len(buffers_info) - 20} more buffers")
        print()
        
        # 查找纹理相关 chunks
        print("=== Texture-Related Chunks ===")
        texture_chunks = find_texture_related_chunks(sd_file)
        
        for tc in texture_chunks[:20]:
            print(f"  Chunk {tc['index']}: {tc['name']}")
            
            if args.analyze_chunks:
                structure = analyze_chunk_structure(tc['chunk'], max_depth=3)
                print(f"    Structure: {json.dumps(structure, indent=6, default=str)[:500]}...")
        
        if len(texture_chunks) > 20:
            print(f"  ... and {len(texture_chunks) - 20} more texture chunks")
        print()
        
        # 查找 InitialContents chunks
        print("=== InitialContents Chunks ===")
        initial_contents = find_initial_contents_chunks(sd_file)
        analysis['initial_contents'] = [
            {'index': ic['index'], 'name': ic['name']} 
            for ic in initial_contents
        ]
        
        for ic in initial_contents[:10]:
            print(f"  Chunk {ic['index']}: {ic['name']}")
            
            if args.analyze_chunks:
                structure = analyze_chunk_structure(ic['chunk'], max_depth=4)
                # 查找 buffer 引用
                print(f"    Full structure:")
                print(json.dumps(structure, indent=4, default=str)[:2000])
        
        if len(initial_contents) > 10:
            print(f"  ... and {len(initial_contents) - 10} more InitialContents chunks")
        print()
        
        # 导出 buffers
        if args.dump_buffers:
            print("=== Dumping Buffers ===")
            buffers_dir = output_dir / "buffers"
            buffers_dir.mkdir(exist_ok=True)
            
            for i, buf_info in enumerate(buffers_info):
                if buf_info['size'] > 0:
                    ext = ".bin"
                    if buf_info['type'] == "PNG image":
                        ext = ".png"
                    elif buf_info['type'] == "JPEG image":
                        ext = ".jpg"
                    elif buf_info['type'] == "DDS texture":
                        ext = ".dds"
                    
                    output_path = buffers_dir / f"buffer_{i:04d}_{buf_info['size']}{ext}"
                    dump_buffer_to_file(sd_file, i, output_path)
        
        # 输出 JSON 分析结果
        if args.json_output:
            with open(args.json_output, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, default=str)
            print(f"Analysis saved to {args.json_output}")
        
        # 清理
        cap.Shutdown()
        
        print()
        print("=== Summary ===")
        print(f"Total chunks: {len(sd_file.chunks)}")
        print(f"Total buffers: {len(sd_file.buffers)}")
        print(f"Texture-related chunks: {len(texture_chunks)}")
        print(f"InitialContents chunks: {len(initial_contents)}")
        print()
        print("SUCCESS: Structured data extracted without GPU!")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        rd.ShutdownReplay()


if __name__ == '__main__':
    sys.exit(main())
