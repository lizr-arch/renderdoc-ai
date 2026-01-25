#!/usr/bin/env python3
"""
测试纹理元数据提取功能

Usage:
    py -3 test_texture_extract.py <rdc_file>
"""

import sys
import os
from pathlib import Path

# 添加当前目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from rdc_parser import RDCParser, extract_textures, TextureInfo



def format_size_mb(size_mb: float) -> str:
    """格式化大小"""
    if size_mb < 1:
        return f"{size_mb * 1024:.1f} KB"
    return f"{size_mb:.2f} MB"


def print_texture_summary(textures: list):
    """打印纹理摘要"""
    print(f"\n{'='*80}")
    print(f"纹理元数据摘要")
    print(f"{'='*80}")
    print(f"总计提取: {len(textures)} 个纹理\n")
    
    # 统计
    render_targets = [t for t in textures if t.is_render_target]
    depth_stencils = [t for t in textures if t.is_depth_stencil]
    sampled = [t for t in textures if t.usage & 0x04]  # SAMPLED
    storage = [t for t in textures if t.usage & 0x08]  # STORAGE
    
    print(f"按用途分类:")
    print(f"  - 渲染目标 (Color/Depth Attachment): {len(render_targets)}")
    print(f"  - 深度/模板: {len(depth_stencils)}")
    print(f"  - 采样纹理 (SAMPLED): {len(sampled)}")
    print(f"  - 存储纹理 (STORAGE): {len(storage)}")
    
    # 按格式统计
    format_counts = {}
    for t in textures:
        fname = t.format_name
        format_counts[fname] = format_counts.get(fname, 0) + 1
    
    print(f"\n按格式分类 (Top 10):")
    for fname, count in sorted(format_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  - {fname}: {count}")
    
    # 按尺寸统计
    size_buckets = {"<= 256": 0, "257-1024": 0, "1025-2048": 0, "> 2048": 0}
    for t in textures:
        max_dim = max(t.width, t.height)
        if max_dim <= 256:
            size_buckets["<= 256"] += 1
        elif max_dim <= 1024:
            size_buckets["257-1024"] += 1
        elif max_dim <= 2048:
            size_buckets["1025-2048"] += 1
        else:
            size_buckets["> 2048"] += 1
    
    print(f"\n按最大尺寸分类:")
    for bucket, count in size_buckets.items():
        print(f"  - {bucket}: {count}")
    
    # 估算总大小
    total_mb = sum(t.estimated_size_mb for t in textures)
    print(f"\n估算总显存占用: {format_size_mb(total_mb)}")


def print_texture_table(textures: list, limit: int = 50):
    """打印纹理表格"""
    print(f"\n{'='*120}")
    print(f"纹理详细列表 (前 {min(limit, len(textures))} 个)")
    print(f"{'='*120}")
    
    # 表头
    header = f"{'ID':>8} | {'Type':>4} | {'Dimensions':>20} | {'Format':>30} | {'Usage':>25} | {'Est.Size':>10}"
    print(header)
    print("-" * 120)
    
    # 按估算大小排序（大的优先）
    sorted_textures = sorted(textures, key=lambda t: -t.estimated_size_mb)
    
    for tex in sorted_textures[:limit]:
        usage_str = ",".join(tex.usage_flags) if tex.usage_flags else "-"
        if len(usage_str) > 25:
            usage_str = usage_str[:22] + "..."
        
        print(f"{tex.resource_id:>8} | {tex.type_name:>4} | {tex.dimensions:>20} | "
              f"{tex.format_name:>30} | {usage_str:>25} | {format_size_mb(tex.estimated_size_mb):>10}")
    
    if len(textures) > limit:
        print(f"\n... 还有 {len(textures) - limit} 个纹理未显示")


def print_render_targets(textures: list):
    """打印渲染目标列表"""
    render_targets = [t for t in textures if t.is_render_target]
    
    print(f"\n{'='*100}")
    print(f"渲染目标 (Render Targets) - 共 {len(render_targets)} 个")
    print(f"{'='*100}")
    
    if not render_targets:
        print("未找到渲染目标")
        return
    
    # 按尺寸排序
    sorted_rts = sorted(render_targets, key=lambda t: -(t.width * t.height))
    
    for rt in sorted_rts[:30]:
        rt_type = "Depth" if rt.is_depth_stencil else "Color"
        msaa = f" ({rt.msaa_desc})" if rt.msaa_desc else ""
        print(f"  [{rt_type:>5}] {rt.dimensions:>15}{msaa:<12} - {rt.format_name}")


def main():
    if len(sys.argv) < 2:
        print("Usage: py -3 test_texture_extract.py <rdc_file>")
        print("\nExample:")
        print("  py -3 test_texture_extract.py D:\\renderdoc\\goog-pixel-9\\g145.rdc")
        sys.exit(1)
    
    rdc_path = sys.argv[1]
    
    if not os.path.exists(rdc_path):
        print(f"Error: File not found: {rdc_path}")
        sys.exit(1)
    
    print(f"解析 RDC 文件: {rdc_path}")
    print(f"文件大小: {os.path.getsize(rdc_path) / 1024 / 1024:.2f} MB")
    
    try:
        # 提取纹理
        print("\n正在提取纹理元数据...")
        textures = extract_textures(rdc_path)
        
        if not textures:
            print("\n[WARNING] 未能提取任何纹理元数据")
            print("可能原因:")
            print("  1. RenderDoc 序列化格式与解析器不兼容")
            print("  2. RDC 文件中没有 vkCreateImage 调用")
            print("\n将尝试调试模式，输出原始 chunk 信息...")
            
            # 调试模式
            with RDCParser(rdc_path) as parser:
                parser.parse_header()
                fc_data = parser.get_frame_capture_data()
                chunks = parser.parse_chunks(fc_data)
                
                # 统计 chunk 类型
                chunk_counts = {}
                for chunk in chunks:
                    name = chunk.chunk_name
                    chunk_counts[name] = chunk_counts.get(name, 0) + 1
                
                print(f"\nChunk 类型统计 (Top 20):")
                for name, count in sorted(chunk_counts.items(), key=lambda x: -x[1])[:20]:
                    print(f"  {name}: {count}")
                
                # 查找 vkCreateImage
                create_image_chunks = [c for c in chunks if 'CreateImage' in c.chunk_name]
                print(f"\nvkCreateImage chunks: {len(create_image_chunks)}")
                
                if create_image_chunks:
                    print("\n前 5 个 vkCreateImage chunk 的原始数据:")
                    for i, chunk in enumerate(create_image_chunks[:5]):
                        print(f"\n  Chunk {i}: offset={chunk.data_offset}, length={chunk.length}")
                        # 打印前 128 字节的十六进制
                        chunk_data = fc_data[chunk.data_offset:chunk.data_offset + min(128, chunk.length)]
                        hex_str = chunk_data.hex()
                        # 按 16 字节分行
                        for j in range(0, len(hex_str), 32):
                            line_offset = j // 2
                            print(f"    {line_offset:04x}: {hex_str[j:j+32]}")
            
            sys.exit(1)
        
        # 打印结果
        print_texture_summary(textures)
        print_render_targets(textures)
        print_texture_table(textures)
        
        print(f"\n[OK] 纹理元数据提取成功!")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
