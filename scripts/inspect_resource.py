#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inspect_resource.py - 资源内容检查 CLI 工具

在指定事件点查看 Buffer/Texture 的具体数据内容。

用法:
    # 通过 renderdoccmd 运行
    renderdoccmd.exe pythonscript inspect_resource.py capture.rdc --resource 3002 --event 200
    
    # 查看帮助
    python inspect_resource.py --help
"""

import sys
import os
import argparse
import struct
import io

# 添加父目录到 path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# 处理 stdout 编码
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass


def create_argument_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description='RDC Resource Inspector - 查看 GPU 资源数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看 Buffer 的十六进制 Dump
  inspect_resource.py capture.rdc --resource 3002 --event 200

  # 解析为 float4 数组
  inspect_resource.py capture.rdc --resource 3002 --event 200 --format float4

  # 解析为索引缓冲区
  inspect_resource.py capture.rdc --resource 3002 --event 200 --format index16

  # 导出为 CSV
  inspect_resource.py capture.rdc --resource 3002 --event 200 --export buffer.csv

  # 列出所有资源
  inspect_resource.py capture.rdc --list
        """
    )
    
    parser.add_argument('rdc_file', nargs='?', help='RDC 捕获文件路径')
    parser.add_argument('-r', '--resource', type=int, help='资源 ID')
    parser.add_argument('-e', '--event', type=int, help='事件 ID')
    parser.add_argument('-f', '--format', 
                        choices=['hex', 'float1', 'float2', 'float3', 'float4', 
                                'int1', 'int2', 'int3', 'int4',
                                'index16', 'index32', 'raw'],
                        default='hex',
                        help='数据显示格式 (default: hex)')
    parser.add_argument('--offset', type=int, default=0, help='读取起始偏移')
    parser.add_argument('--length', type=int, default=0, help='读取长度 (0=全部)')
    parser.add_argument('--export', '-o', help='导出文件路径 (.csv, .json, .txt)')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有资源')
    parser.add_argument('--texture', '-t', action='store_true', help='作为纹理读取')
    parser.add_argument('--mip', type=int, default=0, help='Mipmap 级别 (纹理)')
    parser.add_argument('--slice', type=int, default=0, help='数组 slice (纹理)')
    parser.add_argument('--max-lines', type=int, default=64, help='最大显示行数')
    
    return parser


def list_resources(controller):
    """列出所有资源"""
    print("\n" + "=" * 80)
    print("  RESOURCES LIST")
    print("=" * 80)
    
    try:
        resources = controller.GetResources()
        
        # 分类统计
        buffers = []
        textures = []
        others = []
        
        for res in resources:
            res_id = res.resourceId.id if hasattr(res.resourceId, 'id') else res.resourceId
            name = res.name if hasattr(res, 'name') else str(res_id)
            res_type = str(res.type) if hasattr(res, 'type') else 'Unknown'
            
            info = {
                'id': res_id,
                'name': name,
                'type': res_type
            }
            
            if 'Buffer' in res_type or 'buffer' in name.lower():
                buffers.append(info)
            elif 'Texture' in res_type or 'texture' in name.lower():
                textures.append(info)
            else:
                others.append(info)
        
        print(f"\n📦 Buffers ({len(buffers)}):")
        print("-" * 60)
        for buf in sorted(buffers, key=lambda x: x['id'])[:50]:
            print(f"  [{buf['id']:6d}] {buf['name'][:50]}")
        if len(buffers) > 50:
            print(f"  ... and {len(buffers) - 50} more")
        
        print(f"\n🖼️  Textures ({len(textures)}):")
        print("-" * 60)
        for tex in sorted(textures, key=lambda x: x['id'])[:50]:
            print(f"  [{tex['id']:6d}] {tex['name'][:50]}")
        if len(textures) > 50:
            print(f"  ... and {len(textures) - 50} more")
        
        print(f"\n📎 Others ({len(others)}):")
        print("-" * 60)
        for other in sorted(others, key=lambda x: x['id'])[:20]:
            print(f"  [{other['id']:6d}] {other['type']}: {other['name'][:40]}")
        if len(others) > 20:
            print(f"  ... and {len(others) - 20} more")
        
        print(f"\n总计: {len(resources)} 个资源")
        
    except Exception as e:
        print(f"Error listing resources: {e}")


def format_hex_dump(data: bytes, bytes_per_line: int = 16, max_lines: int = 64) -> str:
    """格式化十六进制 Dump"""
    if not data:
        return "(empty)"
    
    lines = []
    total_bytes = min(len(data), bytes_per_line * max_lines)
    
    for i in range(0, total_bytes, bytes_per_line):
        chunk = data[i:i+bytes_per_line]
        
        addr = f"{i:08X}:"
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        hex_part = hex_part.ljust(bytes_per_line * 3 - 1)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        
        lines.append(f"{addr} {hex_part}  {ascii_part}")
    
    if len(data) > total_bytes:
        lines.append(f"... ({len(data) - total_bytes} more bytes)")
    
    return '\n'.join(lines)


def format_as_floats(data: bytes, components: int, max_elements: int = 100) -> str:
    """格式化为浮点数"""
    if not data:
        return "(empty)"
    
    lines = []
    element_size = 4 * components
    count = min(len(data) // element_size, max_elements)
    
    for i in range(count):
        offset = i * element_size
        values = []
        for j in range(components):
            try:
                value = struct.unpack('<f', data[offset + j*4:offset + (j+1)*4])[0]
                values.append(f"{value:12.6f}")
            except struct.error:
                values.append("       ???")
        lines.append(f"[{i:4d}]: {', '.join(values)}")
    
    total = len(data) // element_size
    if total > count:
        lines.append(f"... ({total - count} more elements)")
    
    return '\n'.join(lines)


def format_as_ints(data: bytes, components: int, max_elements: int = 100) -> str:
    """格式化为整数"""
    if not data:
        return "(empty)"
    
    lines = []
    element_size = 4 * components
    count = min(len(data) // element_size, max_elements)
    
    for i in range(count):
        offset = i * element_size
        values = []
        for j in range(components):
            try:
                value = struct.unpack('<i', data[offset + j*4:offset + (j+1)*4])[0]
                values.append(f"{value:12d}")
            except struct.error:
                values.append("       ???")
        lines.append(f"[{i:4d}]: {', '.join(values)}")
    
    total = len(data) // element_size
    if total > count:
        lines.append(f"... ({total - count} more elements)")
    
    return '\n'.join(lines)


def format_as_indices(data: bytes, is_32bit: bool, max_elements: int = 200) -> str:
    """格式化为索引"""
    if not data:
        return "(empty)"
    
    size = 4 if is_32bit else 2
    fmt = '<I' if is_32bit else '<H'
    count = min(len(data) // size, max_elements)
    
    indices = []
    for i in range(count):
        offset = i * size
        value = struct.unpack(fmt, data[offset:offset+size])[0]
        indices.append(value)
    
    # 按三角形分组显示
    lines = []
    for i in range(0, len(indices), 3):
        tri = indices[i:i+3]
        if len(tri) == 3:
            lines.append(f"Tri {i//3:4d}: {tri[0]:6d}, {tri[1]:6d}, {tri[2]:6d}")
        else:
            lines.append(f"Partial:  {', '.join(str(v) for v in tri)}")
    
    total = len(data) // size
    if total > count:
        lines.append(f"... ({(total - count)//3} more triangles)")
    
    return '\n'.join(lines)


def inspect_buffer(controller, resource_id: int, event_id: int, args):
    """检查 Buffer 数据"""
    print(f"\n{'=' * 80}")
    print(f"  BUFFER INSPECTION")
    print(f"{'=' * 80}")
    print(f"  Resource ID: {resource_id}")
    print(f"  Event ID:    {event_id}")
    print(f"  Format:      {args.format}")
    print(f"{'=' * 80}\n")
    
    # 跳转到事件
    controller.SetFrameEvent(event_id, True)
    
    # 创建 ResourceId
    try:
        import renderdoc as rd
        res_id = rd.ResourceId()
        res_id.id = resource_id
    except ImportError:
        print("Warning: Running without RenderDoc module")
        return
    
    # 获取资源名称
    resource_name = f"Resource_{resource_id}"
    try:
        resources = controller.GetResources()
        for res in resources:
            rid = res.resourceId.id if hasattr(res.resourceId, 'id') else res.resourceId
            if rid == resource_id:
                resource_name = res.name
                break
    except Exception:
        pass
    
    print(f"Resource Name: {resource_name}")
    
    # 读取数据
    try:
        raw_data = bytes(controller.GetBufferData(res_id, args.offset, args.length))
        print(f"Data Size:     {len(raw_data)} bytes")
        print(f"{'─' * 60}")
        
        # 根据格式显示
        if args.format == 'hex' or args.format == 'raw':
            print(format_hex_dump(raw_data, max_lines=args.max_lines))
        elif args.format.startswith('float'):
            components = int(args.format[-1])
            print(format_as_floats(raw_data, components, args.max_lines))
        elif args.format.startswith('int'):
            components = int(args.format[-1])
            print(format_as_ints(raw_data, components, args.max_lines))
        elif args.format == 'index16':
            print(format_as_indices(raw_data, is_32bit=False, max_elements=args.max_lines * 3))
        elif args.format == 'index32':
            print(format_as_indices(raw_data, is_32bit=True, max_elements=args.max_lines * 3))
        
        # 导出
        if args.export:
            export_data(raw_data, args.export, args.format, resource_id, event_id, resource_name)
            
    except Exception as e:
        print(f"Error reading buffer: {e}")
        import traceback
        traceback.print_exc()


def inspect_texture(controller, resource_id: int, event_id: int, args):
    """检查 Texture 数据"""
    print(f"\n{'=' * 80}")
    print(f"  TEXTURE INSPECTION")
    print(f"{'=' * 80}")
    print(f"  Resource ID: {resource_id}")
    print(f"  Event ID:    {event_id}")
    print(f"  Mip Level:   {args.mip}")
    print(f"  Slice:       {args.slice}")
    print(f"{'=' * 80}\n")
    
    # 跳转到事件
    controller.SetFrameEvent(event_id, True)
    
    try:
        import renderdoc as rd
        res_id = rd.ResourceId()
        res_id.id = resource_id
        
        sub = rd.Subresource()
        sub.mip = args.mip
        sub.slice = args.slice
        sub.sample = 0
        
        # 获取纹理信息
        tex_desc = controller.GetTexture(res_id)
        print(f"Texture Info:")
        print(f"  Width:  {tex_desc.width}")
        print(f"  Height: {tex_desc.height}")
        print(f"  Depth:  {tex_desc.depth}")
        print(f"  Format: {tex_desc.format.Name()}")
        print(f"  Mips:   {tex_desc.mips}")
        print(f"  Arrays: {tex_desc.arraysize}")
        print(f"{'─' * 60}")
        
        # 读取数据
        raw_data = bytes(controller.GetTextureData(res_id, sub))
        print(f"Data Size: {len(raw_data)} bytes")
        
        # 显示十六进制
        print(format_hex_dump(raw_data, max_lines=args.max_lines))
        
        # 导出
        if args.export:
            export_texture_data(raw_data, args.export, tex_desc, resource_id, event_id)
            
    except Exception as e:
        print(f"Error reading texture: {e}")
        import traceback
        traceback.print_exc()


def export_data(data: bytes, filepath: str, format_type: str, 
                resource_id: int, event_id: int, resource_name: str):
    """导出数据到文件"""
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == '.csv':
            # CSV 导出
            with open(filepath, 'w', encoding='utf-8') as f:
                if format_type.startswith('float'):
                    components = int(format_type[-1])
                    headers = [f"v{i}" for i in range(components)]
                    f.write(','.join(headers) + '\n')
                    
                    element_size = 4 * components
                    count = len(data) // element_size
                    
                    for i in range(count):
                        offset = i * element_size
                        values = []
                        for j in range(components):
                            value = struct.unpack('<f', data[offset + j*4:offset + (j+1)*4])[0]
                            values.append(str(value))
                        f.write(','.join(values) + '\n')
                        
                elif format_type in ('index16', 'index32'):
                    size = 4 if format_type == 'index32' else 2
                    fmt = '<I' if format_type == 'index32' else '<H'
                    f.write('index\n')
                    
                    count = len(data) // size
                    for i in range(count):
                        offset = i * size
                        value = struct.unpack(fmt, data[offset:offset+size])[0]
                        f.write(f'{value}\n')
                else:
                    # 默认按字节导出
                    f.write('offset,byte\n')
                    for i, b in enumerate(data):
                        f.write(f'{i},{b}\n')
                        
            print(f"\n✓ Exported to {filepath}")
            
        elif ext == '.json':
            import json
            import base64
            
            output = {
                "resource_id": resource_id,
                "resource_name": resource_name,
                "event_id": event_id,
                "size_bytes": len(data),
                "format": format_type,
                "data_base64": base64.b64encode(data).decode('ascii')
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)
                
            print(f"\n✓ Exported to {filepath}")
            
        elif ext == '.bin':
            # 原始二进制
            with open(filepath, 'wb') as f:
                f.write(data)
            print(f"\n✓ Exported raw binary to {filepath}")
            
        else:
            # 文本 hex dump
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Resource: {resource_name}\n")
                f.write(f"Resource ID: {resource_id}\n")
                f.write(f"Event ID: {event_id}\n")
                f.write(f"Size: {len(data)} bytes\n")
                f.write("-" * 60 + "\n")
                f.write(format_hex_dump(data, max_lines=99999))
                
            print(f"\n✓ Exported hex dump to {filepath}")
            
    except Exception as e:
        print(f"Error exporting: {e}")


def export_texture_data(data: bytes, filepath: str, tex_desc, resource_id: int, event_id: int):
    """导出纹理数据"""
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext in ('.png', '.jpg', '.bmp'):
            # 尝试使用 PIL 保存图片
            try:
                from PIL import Image
                import numpy as np
                
                width = tex_desc.width
                height = tex_desc.height
                
                # 假设 RGBA8 格式
                expected_size = width * height * 4
                if len(data) >= expected_size:
                    arr = np.frombuffer(data[:expected_size], dtype=np.uint8)
                    arr = arr.reshape((height, width, 4))
                    img = Image.fromarray(arr, 'RGBA')
                    img.save(filepath)
                    print(f"\n✓ Exported texture to {filepath}")
                else:
                    print(f"Warning: Data size mismatch, expected {expected_size}, got {len(data)}")
                    print("Saving raw binary instead")
                    with open(filepath + '.bin', 'wb') as f:
                        f.write(data)
                        
            except ImportError:
                print("PIL not available, saving raw binary")
                with open(filepath + '.bin', 'wb') as f:
                    f.write(data)
        else:
            # 保存原始数据
            with open(filepath, 'wb') as f:
                f.write(data)
            print(f"\n✓ Exported raw texture data to {filepath}")
            
    except Exception as e:
        print(f"Error exporting texture: {e}")


def main():
    """主函数"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 检查是否在 RenderDoc 环境中运行
    try:
        import renderdoc as rd
        
        # 检查是否有打开的 capture
        if hasattr(rd, 'GetReplayController'):
            controller = rd.GetReplayController()
        else:
            # 需要手动加载
            if not args.rdc_file:
                print("Error: RDC file path required")
                parser.print_help()
                return 1
            
            # 这部分代码需要在 renderdoccmd pythonscript 环境中运行
            print(f"Loading {args.rdc_file}...")
            
            cap, status = rd.OpenCaptureFile()
            if status != rd.ResultCode.Succeeded:
                print(f"Failed to create capture file: {status}")
                return 1
            
            status = cap.OpenFile(args.rdc_file, '', None)
            if status != rd.ResultCode.Succeeded:
                print(f"Failed to open {args.rdc_file}: {status}")
                return 1
            
            if not cap.LocalReplaySupport():
                print("Capture cannot be replayed locally")
                return 1
            
            controller, status = cap.OpenCapture(rd.ReplayOptions(), None)
            if status != rd.ResultCode.Succeeded:
                print(f"Failed to open replay: {status}")
                return 1
        
        print(f"RenderDoc API Version: {rd.GetVersionString()}")
        
        # 执行操作
        if args.list:
            list_resources(controller)
        elif args.resource is not None:
            if args.event is None:
                # 获取第一个 draw call 的事件 ID
                draws = controller.GetDrawcalls()
                if draws:
                    args.event = draws[0].eventId
                    print(f"Using first draw event: {args.event}")
                else:
                    print("Error: --event required")
                    return 1
            
            if args.texture:
                inspect_texture(controller, args.resource, args.event, args)
            else:
                inspect_buffer(controller, args.resource, args.event, args)
        else:
            parser.print_help()
            return 1
        
        return 0
        
    except ImportError:
        print("=" * 60)
        print("ERROR: RenderDoc Python module not available")
        print("=" * 60)
        print()
        print("This script must be run through RenderDoc:")
        print()
        print("  renderdoccmd.exe pythonscript inspect_resource.py \\")
        print("      capture.rdc --resource 3002 --event 200")
        print()
        print("Or run with --help to see all options:")
        print("  python inspect_resource.py --help")
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
