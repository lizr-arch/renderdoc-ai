#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resource Inspector CLI - 资源检查命令行工具
==========================================

用于检查 RDC 文件中的 Buffer 和 Texture 资源数据。

用法:
    python inspect_resource.py <rdc_file> --list                    # 列出所有资源
    python inspect_resource.py <rdc_file> --buffer <id> --event <eid>  # 查看 Buffer
    python inspect_resource.py <rdc_file> --texture <id> --event <eid> # 查看 Texture
    python inspect_resource.py <rdc_file> --export <id> --output <file> # 导出资源
"""

import sys
import os
import argparse
import json

# 添加路径
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# 尝试导入 renderdoc
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False
    print("[Warning] renderdoc module not found. Running in demo mode.")


def load_capture(rdc_path: str):
    """加载 RDC 文件并返回 ReplayController"""
    if not HAS_RENDERDOC:
        return None, None
        
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_path, '', None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"[Error] Failed to open capture: {status}")
        return None, None
        
    if not cap.LocalReplaySupport():
        print("[Error] Capture does not support local replay")
        return cap, None
        
    # 创建 ReplayController
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    if result[0] != rd.ResultCode.Succeeded:
        print(f"[Error] Failed to open replay: {result[0]}")
        return cap, None
        
    return cap, result[1]


def list_resources(controller, resource_type: str = None):
    """列出所有资源"""
    from core.resource_inspector import ResourceInspector, ResourceType
    
    inspector = ResourceInspector(controller)
    
    type_filter = None
    if resource_type:
        type_map = {
            'buffer': ResourceType.BUFFER,
            'texture': ResourceType.TEXTURE_2D,
            'texture2d': ResourceType.TEXTURE_2D,
            'texture3d': ResourceType.TEXTURE_3D,
        }
        type_filter = type_map.get(resource_type.lower())
    
    resources = inspector.list_resources(type_filter)
    
    print(f"\n{'='*60}")
    print(f"Found {len(resources)} resources")
    print(f"{'='*60}\n")
    
    # 分类显示
    buffers = [r for r in resources if r.resource_type == ResourceType.BUFFER]
    textures = [r for r in resources if r.resource_type != ResourceType.BUFFER]
    
    if buffers:
        print(f"Buffers ({len(buffers)}):")
        print("-" * 50)
        for r in buffers[:50]:  # 限制显示数量
            print(f"  ID: {r.resource_id:8d}  Size: {r.size:12,d} bytes  Name: {r.name}")
        if len(buffers) > 50:
            print(f"  ... and {len(buffers) - 50} more")
        print()
        
    if textures:
        print(f"Textures ({len(textures)}):")
        print("-" * 50)
        for r in textures[:50]:
            dims = f"{r.width}x{r.height}"
            if r.depth > 1:
                dims += f"x{r.depth}"
            print(f"  ID: {r.resource_id:8d}  {dims:16s}  Format: {r.format:24s}  Name: {r.name}")
        if len(textures) > 50:
            print(f"  ... and {len(textures) - 50} more")
        print()


def inspect_buffer(controller, resource_id: int, event_id: int, output_format: str = 'hex'):
    """检查 Buffer 数据"""
    from core.resource_inspector import ResourceInspector, BufferFormatParser, format_buffer_preview
    
    inspector = ResourceInspector(controller)
    parser = BufferFormatParser()
    
    print(f"\n{'='*60}")
    print(f"Inspecting Buffer {resource_id} at Event {event_id}")
    print(f"{'='*60}\n")
    
    # 获取数据
    buffer_data = inspector.get_buffer_data(resource_id, event_id)
    
    if buffer_data is None:
        print("[Error] Failed to read buffer data")
        return
        
    print(f"Buffer Size: {buffer_data.size:,} bytes")
    print()
    
    if output_format == 'hex':
        print("Hex Dump:")
        print("-" * 50)
        print(parser.hex_dump(buffer_data.data, max_lines=32))
        
    elif output_format == 'float':
        print("As float4 vectors:")
        print("-" * 50)
        floats = parser.parse_as_floats(buffer_data.data, 4)
        for i, vec in enumerate(floats[:100]):
            print(f"[{i:6d}] ({vec[0]:12.6f}, {vec[1]:12.6f}, {vec[2]:12.6f}, {vec[3]:12.6f})")
        if len(floats) > 100:
            print(f"... ({len(floats) - 100} more vectors)")
            
    elif output_format == 'index16':
        print("As 16-bit indices:")
        print("-" * 50)
        indices = parser.parse_as_indices(buffer_data.data, 'R16_UINT')
        # 显示为三角形
        for i in range(0, min(len(indices), 300), 3):
            if i + 2 < len(indices):
                print(f"Triangle {i//3:6d}: {indices[i]:6d}, {indices[i+1]:6d}, {indices[i+2]:6d}")
        if len(indices) > 300:
            print(f"... ({len(indices) - 300} more indices)")
            
    elif output_format == 'index32':
        print("As 32-bit indices:")
        print("-" * 50)
        indices = parser.parse_as_indices(buffer_data.data, 'R32_UINT')
        for i in range(0, min(len(indices), 300), 3):
            if i + 2 < len(indices):
                print(f"Triangle {i//3:6d}: {indices[i]:6d}, {indices[i+1]:6d}, {indices[i+2]:6d}")
        if len(indices) > 300:
            print(f"... ({len(indices) - 300} more indices)")
            
    else:
        print(format_buffer_preview(buffer_data.data))


def inspect_texture(controller, resource_id: int, event_id: int):
    """检查 Texture 数据"""
    from core.resource_inspector import ResourceInspector
    
    inspector = ResourceInspector(controller)
    
    print(f"\n{'='*60}")
    print(f"Inspecting Texture {resource_id} at Event {event_id}")
    print(f"{'='*60}\n")
    
    # 获取纹理信息
    info = inspector.get_resource_info(resource_id)
    if info:
        print(f"Name: {info.name}")
        print(f"Dimensions: {info.width} x {info.height} x {info.depth}")
        print(f"Format: {info.format}")
        print(f"Mip Levels: {info.mip_levels}")
        print(f"Array Size: {info.array_size}")
        print()
    
    # 获取纹理数据
    texture_data = inspector.get_texture_data(resource_id, event_id)
    
    if texture_data is None:
        print("[Error] Failed to read texture data")
        return
        
    print(f"Data Size: {len(texture_data.data):,} bytes")
    
    # 显示部分数据预览
    from core.resource_inspector import BufferFormatParser
    parser = BufferFormatParser()
    print()
    print("Raw Data Preview:")
    print("-" * 50)
    print(parser.hex_dump(texture_data.data, max_lines=16))


def export_resource(controller, resource_id: int, event_id: int, output_path: str, format_type: str):
    """导出资源到文件"""
    from core.resource_inspector import ResourceInspector, BufferFormatParser
    
    inspector = ResourceInspector(controller)
    
    # 获取资源信息以判断类型
    info = inspector.get_resource_info(resource_id)
    
    if info is None:
        print(f"[Error] Resource {resource_id} not found")
        return
        
    from core.resource_inspector import ResourceType
    
    if info.resource_type == ResourceType.BUFFER:
        # 导出 Buffer
        buffer_data = inspector.get_buffer_data(resource_id, event_id)
        if buffer_data is None:
            print("[Error] Failed to read buffer data")
            return
            
        if format_type == 'bin' or format_type == 'raw':
            with open(output_path, 'wb') as f:
                f.write(buffer_data.data)
            print(f"[OK] Exported {len(buffer_data.data):,} bytes to {output_path}")
            
        elif format_type == 'json':
            parser = BufferFormatParser()
            floats = parser.parse_as_floats(buffer_data.data, 4)
            data = {
                'resource_id': resource_id,
                'event_id': event_id,
                'size': buffer_data.size,
                'float4_count': len(floats),
                'data': [list(v) for v in floats[:1000]]  # 限制大小
            }
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[OK] Exported to {output_path}")
            
        elif format_type == 'csv':
            parser = BufferFormatParser()
            floats = parser.parse_as_floats(buffer_data.data, 4)
            with open(output_path, 'w') as f:
                f.write("index,x,y,z,w\n")
                for i, vec in enumerate(floats):
                    f.write(f"{i},{vec[0]},{vec[1]},{vec[2]},{vec[3]}\n")
            print(f"[OK] Exported {len(floats)} vectors to {output_path}")
            
    else:
        # 导出 Texture
        texture_data = inspector.get_texture_data(resource_id, event_id)
        if texture_data is None:
            print("[Error] Failed to read texture data")
            return
            
        if format_type == 'bin' or format_type == 'raw':
            with open(output_path, 'wb') as f:
                f.write(texture_data.data)
            print(f"[OK] Exported {len(texture_data.data):,} bytes to {output_path}")
        else:
            print(f"[Warning] Texture export as {format_type} not yet implemented")
            print("Use --format bin for raw data export")


def run_demo_mode():
    """演示模式 - 不需要 RenderDoc"""
    from core.resource_inspector import BufferFormatParser, format_buffer_preview
    import struct
    
    print("\n" + "="*60)
    print("DEMO MODE - Testing BufferFormatParser")
    print("="*60 + "\n")
    
    # 创建模拟数据
    parser = BufferFormatParser()
    
    # 模拟顶点数据: Position(float3) + Normal(float3) + UV(float2)
    test_data = b''
    for i in range(10):
        # Position
        test_data += struct.pack('<3f', float(i), float(i*2), float(i*3))
        # Normal
        test_data += struct.pack('<3f', 0.0, 1.0, 0.0)
        # UV
        test_data += struct.pack('<2f', float(i)/10, float(i)/10)
        
    print("1. Testing vertex buffer parsing:")
    print("-" * 50)
    
    layout = [
        {'name': 'POSITION', 'format': 'R32G32B32_FLOAT', 'offset': 0},
        {'name': 'NORMAL', 'format': 'R32G32B32_FLOAT', 'offset': 12},
        {'name': 'TEXCOORD', 'format': 'R32G32_FLOAT', 'offset': 24},
    ]
    
    vertices = parser.parse_vertex_buffer(test_data, layout)
    for i, v in enumerate(vertices[:5]):
        print(f"  Vertex {i}:")
        print(f"    Position: {v['POSITION']}")
        print(f"    Normal:   {v['NORMAL']}")
        print(f"    TexCoord: {v['TEXCOORD']}")
    print()
    
    # 模拟索引数据
    print("2. Testing index buffer parsing:")
    print("-" * 50)
    
    index_data = struct.pack('<12H', 0, 1, 2, 2, 3, 0, 4, 5, 6, 6, 7, 4)
    indices = parser.parse_as_indices(index_data, 'R16_UINT')
    print(f"  Indices: {indices}")
    print(f"  Triangles: ", end='')
    for i in range(0, len(indices), 3):
        print(f"({indices[i]},{indices[i+1]},{indices[i+2]}) ", end='')
    print("\n")
    
    # 模拟常量缓冲区
    print("3. Testing constant buffer parsing:")
    print("-" * 50)
    
    # 模拟 MVP 矩阵
    identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
    cb_data = struct.pack('<16f', *identity)  # World
    cb_data += struct.pack('<16f', *identity)  # View
    cb_data += struct.pack('<16f', *identity)  # Projection
    cb_data += struct.pack('<4f', 1.0, 0.5, 0.2, 1.0)  # Color
    
    cb_layout = [
        {'name': 'WorldMatrix', 'type': 'float4x4', 'offset': 0},
        {'name': 'ViewMatrix', 'type': 'float4x4', 'offset': 64},
        {'name': 'ProjectionMatrix', 'type': 'float4x4', 'offset': 128},
        {'name': 'DiffuseColor', 'type': 'float4', 'offset': 192},
    ]
    
    constants = parser.parse_constant_buffer(cb_data, cb_layout)
    print(f"  WorldMatrix[0]: {constants['WorldMatrix'][0]}")
    print(f"  DiffuseColor: {constants['DiffuseColor']}")
    print()
    
    # Hex dump 测试
    print("4. Testing hex dump:")
    print("-" * 50)
    print(parser.hex_dump(test_data[:64], max_lines=4))
    print()
    
    print("="*60)
    print("Demo completed successfully!")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='RDC Resource Inspector - 检查 RenderDoc 捕获中的资源数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s capture.rdc --list                         列出所有资源
  %(prog)s capture.rdc --list --type buffer           只列出 Buffer
  %(prog)s capture.rdc --buffer 3002 --event 120      查看 Buffer 数据
  %(prog)s capture.rdc --buffer 3002 --event 120 --format float    以浮点数显示
  %(prog)s capture.rdc --texture 5001 --event 200     查看 Texture 信息
  %(prog)s capture.rdc --export 3002 --event 120 --output data.bin  导出数据
  %(prog)s --demo                                     运行演示模式
        """
    )
    
    parser.add_argument('rdc_file', nargs='?', help='RDC 文件路径')
    parser.add_argument('--list', '-l', action='store_true', help='列出资源')
    parser.add_argument('--type', '-t', choices=['buffer', 'texture'], help='资源类型筛选')
    parser.add_argument('--buffer', '-b', type=int, help='Buffer 资源 ID')
    parser.add_argument('--texture', '-T', type=int, help='Texture 资源 ID')
    parser.add_argument('--event', '-e', type=int, default=1, help='事件 ID (默认: 1)')
    parser.add_argument('--format', '-f', 
                        choices=['hex', 'float', 'index16', 'index32', 'json', 'csv', 'bin'],
                        default='hex', help='输出格式')
    parser.add_argument('--export', '-x', type=int, help='导出资源 ID')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--demo', action='store_true', help='运行演示模式（不需要 RDC 文件）')
    
    args = parser.parse_args()
    
    # 演示模式
    if args.demo:
        run_demo_mode()
        return 0
        
    # 检查参数
    if not args.rdc_file:
        parser.print_help()
        return 1
        
    if not os.path.exists(args.rdc_file):
        print(f"[Error] File not found: {args.rdc_file}")
        return 1
        
    # 加载捕获
    cap, controller = load_capture(args.rdc_file)
    
    if controller is None:
        if not HAS_RENDERDOC:
            print("\n[Info] Running demo mode since renderdoc is not available")
            run_demo_mode()
            return 0
        print("[Error] Failed to create replay controller")
        return 1
        
    try:
        if args.list:
            list_resources(controller, args.type)
            
        elif args.buffer is not None:
            inspect_buffer(controller, args.buffer, args.event, args.format)
            
        elif args.texture is not None:
            inspect_texture(controller, args.texture, args.event)
            
        elif args.export is not None:
            if not args.output:
                print("[Error] --output is required for export")
                return 1
            export_resource(controller, args.export, args.event, args.output, args.format)
            
        else:
            parser.print_help()
            
    finally:
        if controller:
            controller.Shutdown()
        if cap:
            cap.Shutdown()
            
    return 0


if __name__ == '__main__':
    sys.exit(main())
