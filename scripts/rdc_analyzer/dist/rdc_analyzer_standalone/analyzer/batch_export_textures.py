#!/usr/bin/env python3
"""
batch_export_textures.py - 纹理批量导出 CLI 工具

从 RenderDoc 捕获文件中批量导出所有纹理。
支持两种模式：
  1. RDC 直接回放模式（需要 GPU + renderdoc.pyd）
  2. XML+ZIP 离线模式（无需 GPU，但需先用 renderdoccmd 转换）

用法:
    # 从 XML+ZIP 导出（推荐，无需 GPU）
    py -3 batch_export_textures.py capture.xml -o ./textures
    
    # 从 RDC 直接导出（需要 GPU）
    py -3 batch_export_textures.py capture.rdc -o ./textures
    
    # 批量处理目录
    py -3 batch_export_textures.py ./captures/ -o ./textures --recursive

转换 RDC 为 XML+ZIP（无需 GPU 提取的前置步骤）:
    renderdoccmd convert -c zip.xml capture.rdc -o capture.xml

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

# 添加父目录到路径（用于独立运行）
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

# 直接导入，避免包层级问题
try:
    from exporters.texture_batch_exporter import (
        create_export_engine,
        generate_html_gallery,
        BatchExportSummary,
        TextureInfo,
        XmlZipExportEngine,
        RdcReplayExportEngine,
        HAS_RENDERDOC,
        DECODER_AVAILABLE
    )
except ImportError:
    # 如果包导入失败，尝试直接导入模块
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "texture_batch_exporter",
        _script_dir / "exporters" / "texture_batch_exporter.py"
    )
    _module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_module)
    
    create_export_engine = _module.create_export_engine
    generate_html_gallery = _module.generate_html_gallery
    BatchExportSummary = _module.BatchExportSummary
    TextureInfo = _module.TextureInfo
    XmlZipExportEngine = _module.XmlZipExportEngine
    RdcReplayExportEngine = _module.RdcReplayExportEngine
    HAS_RENDERDOC = _module.HAS_RENDERDOC
    DECODER_AVAILABLE = _module.DECODER_AVAILABLE


def print_progress(current: int, total: int, texture: TextureInfo):
    """打印进度条"""
    bar_width = 30
    progress = current / total
    filled = int(bar_width * progress)
    bar = '█' * filled + '░' * (bar_width - filled)
    
    # 截断格式名以适应显示
    fmt_short = texture.format[:20] + "..." if len(texture.format) > 23 else texture.format
    
    print(f"\r[{bar}] {current}/{total} ({progress*100:.0f}%) | "
          f"{texture.width}x{texture.height} {fmt_short}",
          end='', flush=True)


def process_single_file(
    input_path: Path,
    output_dir: Path,
    save_png: bool,
    save_bin: bool,
    filter_pattern: Optional[str],
    max_count: int,
    generate_gallery: bool,
    generate_manifest: bool,
    quiet: bool
) -> Optional[BatchExportSummary]:
    """处理单个文件"""
    
    if not quiet:
        print(f"\n{'='*60}")
        print(f"Processing: {input_path.name}")
        print(f"{'='*60}")
    
    try:
        engine = create_export_engine(input_path)
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        return None
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        return None
    
    try:
        # 创建输出目录（以文件名为子目录）
        file_output_dir = output_dir / input_path.stem
        
        # 执行导出
        start_time = time.time()
        summary = engine.export_all(
            output_dir=file_output_dir,
            save_png=save_png,
            save_bin=save_bin,
            filter_pattern=filter_pattern,
            max_count=max_count,
            progress_callback=None if quiet else print_progress
        )
        elapsed = time.time() - start_time
        
        if not quiet:
            print()  # 换行（因为进度条用了 \r）
            print(f"\n✅ Completed in {elapsed:.1f}s")
            print(f"   Total: {summary.total} | Success: {summary.success} | Failed: {summary.failed}")
        
        # 生成图库
        if generate_gallery and summary.success > 0:
            gallery_path = generate_html_gallery(summary, file_output_dir)
            if not quiet:
                print(f"   Gallery: {gallery_path}")
        
        # 生成清单
        if generate_manifest:
            manifest_path = file_output_dir / "manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
            if not quiet:
                print(f"   Manifest: {manifest_path}")
        
        return summary
        
    finally:
        engine.close()


def find_input_files(input_path: Path, recursive: bool) -> List[Path]:
    """查找所有输入文件"""
    if input_path.is_file():
        return [input_path]
    
    if input_path.is_dir():
        patterns = ['*.xml', '*.rdc']
        files = []
        
        for pattern in patterns:
            if recursive:
                files.extend(input_path.rglob(pattern))
            else:
                files.extend(input_path.glob(pattern))
        
        return sorted(set(files))
    
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Batch export textures from RenderDoc captures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export from XML+ZIP (no GPU required)
  py -3 batch_export_textures.py capture.xml -o ./textures
  
  # Export from RDC (requires GPU)
  py -3 batch_export_textures.py capture.rdc -o ./textures
  
  # Batch process directory
  py -3 batch_export_textures.py ./captures/ -o ./textures -r
  
  # Filter by format (only BC7 textures)
  py -3 batch_export_textures.py capture.xml -o ./textures --filter "BC7"
  
  # Export first 10 textures with gallery
  py -3 batch_export_textures.py capture.xml -o ./textures --max 10 --gallery

To convert RDC to XML+ZIP (for GPU-free extraction):
  renderdoccmd convert -c zip.xml capture.rdc -o capture.xml
"""
    )
    
    parser.add_argument(
        "input",
        type=Path,
        help="Input file (.rdc or .xml) or directory"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("./textures_export"),
        help="Output directory (default: ./textures_export)"
    )
    parser.add_argument(
        "--png",
        action="store_true",
        default=True,
        help="Export as PNG (default: True)"
    )
    parser.add_argument(
        "--no-png",
        action="store_true",
        help="Disable PNG export"
    )
    parser.add_argument(
        "--bin",
        action="store_true",
        help="Also save raw binary data"
    )
    parser.add_argument(
        "--filter",
        type=str,
        metavar="REGEX",
        help="Filter textures by format/size (regex, e.g. 'BC7|1024x')"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=-1,
        help="Maximum number of textures to export"
    )
    parser.add_argument(
        "--gallery",
        action="store_true",
        help="Generate HTML gallery preview"
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Generate JSON manifest"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively process subdirectories"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet mode (less output)"
    )
    
    args = parser.parse_args()
    
    # 验证输入
    if not args.input.exists():
        print(f"[ERROR] Input not found: {args.input}")
        return 1
    
    # 检查依赖
    if not args.quiet:
        print("=" * 60)
        print(" Texture Batch Exporter v1.0.0")
        print("=" * 60)
        print(f" Decoder available: {'✓' if DECODER_AVAILABLE else '✗'}")
        print(f" RenderDoc module:  {'✓' if HAS_RENDERDOC else '✗'}")
        print(f" Input: {args.input}")
        print(f" Output: {args.output}")
    
    # 查找输入文件
    input_files = find_input_files(args.input, args.recursive)
    
    if not input_files:
        print(f"[ERROR] No .xml or .rdc files found in: {args.input}")
        return 1
    
    if not args.quiet:
        print(f" Files to process: {len(input_files)}")
    
    # 处理选项
    save_png = not args.no_png
    
    # 处理每个文件
    all_summaries = []
    for input_path in input_files:
        summary = process_single_file(
            input_path=input_path,
            output_dir=args.output,
            save_png=save_png,
            save_bin=args.bin,
            filter_pattern=args.filter,
            max_count=args.max,
            generate_gallery=args.gallery,
            generate_manifest=args.manifest,
            quiet=args.quiet
        )
        if summary:
            all_summaries.append((input_path.name, summary))
    
    # 汇总报告
    if len(all_summaries) > 1 and not args.quiet:
        print("\n" + "=" * 60)
        print(" BATCH SUMMARY")
        print("=" * 60)
        
        total_textures = sum(s.total for _, s in all_summaries)
        total_success = sum(s.success for _, s in all_summaries)
        total_failed = sum(s.failed for _, s in all_summaries)
        
        print(f" Files processed: {len(all_summaries)}")
        print(f" Total textures: {total_textures}")
        print(f" Success: {total_success}")
        print(f" Failed: {total_failed}")
        
        # 保存汇总清单
        summary_path = args.output / "summary.json"
        summary_data = {
            "files_processed": len(all_summaries),
            "total_textures": total_textures,
            "total_success": total_success,
            "total_failed": total_failed,
            "files": [
                {
                    "name": name,
                    "total": s.total,
                    "success": s.success,
                    "failed": s.failed
                }
                for name, s in all_summaries
            ]
        }
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        print(f" Summary: {summary_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
