#!/usr/bin/env python3
"""
端到端测试: 使用真实 RDC 数据测试所有功能

此脚本整合完整工作流:
1. renderdoccmd export 导出纹理
2. renderdoccmd export --xml 导出结构化数据
3. 解析 XML 生成 JSON
4. 生成 HTML 报告

用法:
    py -3 test_e2e_real_data.py <capture.rdc> [output_dir]
    
示例:
    py -3 test_e2e_real_data.py test_captures/test_game.rdc output/test_e2e
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))


def find_renderdoccmd():
    """查找 renderdoccmd 可执行文件"""
    # 可能的路径
    candidates = [
        # 项目构建输出
        Path(__file__).parent.parent.parent / "build/bin/renderdoccmd.exe",
        Path(__file__).parent.parent.parent / "x64/Development/renderdoccmd.exe",
        # 系统安装
        Path(os.environ.get("PROGRAMFILES", "")) / "RenderDoc/renderdoccmd.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/RenderDoc/renderdoccmd.exe",
        # 自定义构建
        Path("D:/Code/git/renderdoc/x64/Development/renderdoccmd.exe"),
    ]
    
    for path in candidates:
        if path.exists():
            return str(path)
    
    # 尝试在 PATH 中查找
    result = shutil.which("renderdoccmd")
    if result:
        return result
    
    return None


def run_renderdoccmd_export(rdc_path: Path, output_dir: Path, renderdoccmd: str):
    """运行 renderdoccmd export 命令导出纹理和 XML"""
    
    # 创建输出目录
    texture_dir = output_dir / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    
    xml_path = output_dir / "capture.xml"
    
    print("\n" + "="*60)
    print("Step 1: Export textures with renderdoccmd")
    print("="*60)
    
    # 导出纹理 (使用正确的命令格式)
    cmd = [
        renderdoccmd, "export",
        "-o", str(texture_dir),
        "-f", "png",
        "-m",  # 导出元数据 JSON
        str(rdc_path)
    ]
    
    print(f"  Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"  [OK] Textures exported to {texture_dir}")
            if result.stdout:
                # 只显示最后几行
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    print(f"    {line}")
            # 统计导出的文件
            png_files = list(texture_dir.glob("*.png"))
            json_files = list(texture_dir.glob("*.json"))
            print(f"    PNG files: {len(png_files)}")
            print(f"    JSON files: {len(json_files)}")
        else:
            print(f"  [WARN] Export returned non-zero: {result.returncode}")
            if result.stderr:
                print(f"    stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("  [ERROR] Command timed out")
    except FileNotFoundError:
        print(f"  [ERROR] renderdoccmd not found at: {renderdoccmd}")
        return None
    
    print("\n" + "="*60)
    print("Step 2: Export XML structure (convert command)")
    print("="*60)
    
    # 导出 XML (使用 convert 命令)
    cmd = [
        renderdoccmd, "convert",
        "-f", str(rdc_path),
        "-o", str(xml_path),
        "-c", "xml"
    ]
    
    print(f"  Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"  [OK] XML exported to {xml_path}")
            if xml_path.exists():
                size_mb = xml_path.stat().st_size / (1024*1024)
                print(f"    Size: {size_mb:.2f} MB")
        else:
            print(f"  [WARN] Convert returned non-zero: {result.returncode}")
            if result.stderr:
                print(f"    stderr: {result.stderr[:500]}")
            if result.stdout:
                print(f"    stdout: {result.stdout[:500]}")
    except subprocess.TimeoutExpired:
        print("  [ERROR] XML export timed out (file may be very large)")
    except Exception as e:
        print(f"  [ERROR] {e}")
    
    return xml_path if xml_path.exists() else None


def parse_xml_to_json(xml_path: Path, output_dir: Path):
    """解析 XML 并生成 JSON"""
    print("\n" + "="*60)
    print("Step 3: Parse XML to JSON")
    print("="*60)
    
    json_path = output_dir / "capture_data.json"
    
    try:
        from parse_rdc_xml import parse_rdc_xml
        
        data = parse_rdc_xml(str(xml_path))
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  [OK] JSON saved to {json_path}")
        print(f"    Events: {data['statistics']['totalEvents']}")
        print(f"    Draw calls: {data['statistics']['totalDrawCalls']}")
        print(f"    Textures: {data['statistics']['totalTextures']}")
        
        return json_path
        
    except Exception as e:
        print(f"  [ERROR] Failed to parse XML: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_html_report(json_path: Path, output_dir: Path, texture_dir: Path = None):
    """生成 HTML 报告"""
    print("\n" + "="*60)
    print("Step 4: Generate HTML Report")
    print("="*60)
    
    html_path = output_dir / "report.html"
    
    try:
        from generate_real_report import (
            load_rdc_data, convert_to_report_format,
            convert_textures_from_rdc, analyze_texture_usage,
            find_duplicate_textures, load_texture_thumbnails,
            merge_thumbnails_to_textures, create_textures_from_export
        )
        from generate_offline_report import generate_offline_html
        
        # 加载 JSON 数据
        rdc_data = load_rdc_data(str(json_path))
        
        # 转换事件数据
        event_data = convert_to_report_format(rdc_data)
        print(f"  Events: {event_data['totalEvents']}")
        print(f"  Draws: {event_data['totalDraws']}")
        print(f"  Passes: {len(event_data['passes'])}")
        
        # 处理纹理数据
        textures = []
        thumbnail_map = {}
        
        if texture_dir and texture_dir.exists():
            print(f"  Loading textures from {texture_dir}...")
            thumbnail_map = load_texture_thumbnails(texture_dir)
            
            if thumbnail_map:
                textures = create_textures_from_export(texture_dir)
                textures = merge_thumbnails_to_textures(textures, thumbnail_map)
                print(f"    Loaded {len(textures)} textures with thumbnails")
        
        # 如果没有导出纹理，从 XML 解析的数据获取
        if not textures:
            rdc_textures = rdc_data.get("textures", [])
            if rdc_textures:
                textures = convert_textures_from_rdc(rdc_textures)
                print(f"    Using {len(textures)} textures from XML")
        
        # 分析纹理
        usage_analysis = analyze_texture_usage(textures)
        duplicate_analysis = find_duplicate_textures(textures)
        
        # 生成报告
        generate_offline_html(
            textures=textures,
            rdc_name=json_path.stem,
            output_path=str(html_path),
            duplicate_analysis=duplicate_analysis,
            usage_analysis=usage_analysis,
            event_pass_data=event_data,
            frame_thumbnail=None,
        )
        
        print(f"  [OK] HTML report saved to {html_path}")
        
        # 显示文件大小
        if html_path.exists():
            size_mb = html_path.stat().st_size / (1024*1024)
            print(f"    Size: {size_mb:.2f} MB")
        
        return html_path
        
    except Exception as e:
        print(f"  [ERROR] Failed to generate report: {e}")
        import traceback
        traceback.print_exc()
        return None


def verify_report(html_path: Path):
    """验证报告内容"""
    print("\n" + "="*60)
    print("Step 5: Verify Report Content")
    print("="*60)
    
    if not html_path.exists():
        print("  [FAIL] Report file not found")
        return False
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键内容
        checks = [
            ("Event Browser data", '"events":' in content and '"eid":' in content),
            ("API type", '"apiType":' in content),
            ("Draw statistics", '"totalDraws":' in content),
            ("Pass data", '"passes":' in content),
            ("API Call data", '"apiCall":' in content or '"signature":' in content),
            ("Texture data", 'textures' in content.lower()),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "OK" if passed else "FAIL"
            print(f"  [{status}] {check_name}")
            if not passed:
                all_passed = False
        
        # 统计内嵌数据大小
        import re
        data_uris = re.findall(r'data:image/[^"]+', content)
        if data_uris:
            total_b64_size = sum(len(uri) for uri in data_uris)
            print(f"  [INFO] Embedded images: {len(data_uris)}, ~{total_b64_size/1024:.1f} KB base64")
        
        return all_passed
        
    except Exception as e:
        print(f"  [ERROR] Verification failed: {e}")
        return False


def print_summary(output_dir: Path, success: bool):
    """打印测试摘要"""
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    if success:
        print("  Status: SUCCESS")
    else:
        print("  Status: PARTIAL (some steps may have warnings)")
    
    print(f"\n  Output directory: {output_dir}")
    
    if output_dir.exists():
        print("\n  Generated files:")
        for f in sorted(output_dir.rglob("*")):
            if f.is_file():
                size = f.stat().st_size
                if size > 1024*1024:
                    size_str = f"{size/(1024*1024):.2f} MB"
                elif size > 1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size} bytes"
                rel_path = f.relative_to(output_dir)
                print(f"    {rel_path}: {size_str}")


def main():
    print("="*60)
    print("RDC Analyzer End-to-End Test")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 解析参数
    if len(sys.argv) < 2:
        print("\nUsage: test_e2e_real_data.py <capture.rdc> [output_dir]")
        print("\nExample:")
        print("  py -3 test_e2e_real_data.py test_captures/test_game.rdc output/test_e2e")
        sys.exit(1)
    
    rdc_path = Path(sys.argv[1])
    
    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = Path("output") / f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 验证输入
    if not rdc_path.exists():
        print(f"\n[ERROR] RDC file not found: {rdc_path}")
        sys.exit(1)
    
    print(f"\nInput RDC: {rdc_path}")
    print(f"Output dir: {output_dir}")
    
    # 查找 renderdoccmd
    renderdoccmd = find_renderdoccmd()
    if not renderdoccmd:
        print("\n[ERROR] renderdoccmd not found!")
        print("  Tried:")
        print("    - Build output (x64/Development/)")
        print("    - Program Files")
        print("    - PATH")
        sys.exit(1)
    
    print(f"renderdoccmd: {renderdoccmd}")
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 执行测试流程
    success = True
    
    # Step 1-2: Export with renderdoccmd
    xml_path = run_renderdoccmd_export(rdc_path, output_dir, renderdoccmd)
    if not xml_path:
        print("\n[WARN] XML export failed, trying to use existing XML...")
        # 尝试查找现有 XML
        existing_xml = rdc_path.with_suffix('.xml')
        if existing_xml.exists():
            xml_path = existing_xml
            print(f"  Found existing XML: {xml_path}")
        else:
            success = False
    
    # Step 3: Parse XML to JSON
    json_path = None
    if xml_path:
        json_path = parse_xml_to_json(xml_path, output_dir)
        if not json_path:
            success = False
    
    # Step 4: Generate HTML Report
    html_path = None
    if json_path:
        texture_dir = output_dir / "textures"
        html_path = generate_html_report(json_path, output_dir, texture_dir)
        if not html_path:
            success = False
    
    # Step 5: Verify
    if html_path:
        verify_result = verify_report(html_path)
        if not verify_result:
            success = False
    
    # Summary
    print_summary(output_dir, success)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
