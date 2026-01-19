#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC 批量分析脚本 (P3-2)
========================

功能:
- 批量分析目录中的所有 RDC 文件
- 生成汇总报告
- 支持多 GPU 型号对比

使用方法:
    py -3 batch_analyze.py --dir "D:/captures/" --gpu "Mali-G78"
    py -3 batch_analyze.py --files "a.rdc,b.rdc" --gpu "Mali-G710"

注意: 此脚本需要在命令行环境运行（非 RenderDoc Shell）
      需要 renderdoc 模块可用（通过 PYTHONPATH 配置）
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import subprocess

# 配置
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"
MALIOC_PATH = r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe"

# 支持的 GPU 列表
SUPPORTED_GPUS = [
    "Mali-G78", "Mali-G77", "Mali-G710", "Mali-G57", "Mali-G76",
    "Immortalis-G720", "Immortalis-G925", "Mali-G720"
]


def find_rdc_files(directory: str) -> List[Path]:
    """递归查找目录中的所有 RDC 文件"""
    rdc_dir = Path(directory)
    if not rdc_dir.exists():
        print(f"[ERROR] Directory not found: {directory}")
        return []
    
    files = list(rdc_dir.rglob("*.rdc"))
    print(f"[INFO] Found {len(files)} RDC files in {directory}")
    return files


def analyze_rdc_standalone(rdc_path: Path, target_gpu: str, output_dir: Path) -> Optional[Dict]:
    """
    使用独立进程分析单个 RDC 文件
    
    注意: 这是一个占位实现。完整的批量分析需要:
    1. 启动 RenderDoc 无头模式
    2. 或通过 renderdoc Python 模块直接加载
    
    当前版本生成模拟数据用于演示批量报告功能。
    """
    print(f"\n[ANALYZE] {rdc_path.name}")
    print(f"  Target GPU: {target_gpu}")
    
    # 检查文件存在
    if not rdc_path.exists():
        return {"error": f"File not found: {rdc_path}", "success": False}
    
    file_size = rdc_path.stat().st_size
    print(f"  File size: {file_size / 1024 / 1024:.2f} MB")
    
    # 占位：实际分析需要 RenderDoc API
    # TODO: 集成 renderdoc headless API
    return {
        "rdc_file": str(rdc_path),
        "rdc_name": rdc_path.name,
        "target_gpu": target_gpu,
        "file_size_mb": file_size / 1024 / 1024,
        "status": "pending_manual_analysis",
        "message": "需要在 RenderDoc Python Shell 中运行完整分析",
        "timestamp": datetime.now().isoformat()
    }


def generate_batch_report(results: List[Dict], output_dir: Path) -> Path:
    """生成批量分析汇总报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"batch_report_{timestamp}.html"
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mali Batch Analysis Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #16213e; color: #00d4ff; }}
        tr:hover {{ background: #16213e; }}
        .status-ok {{ color: #4ecca3; }}
        .status-pending {{ color: #f39c12; }}
        .status-error {{ color: #ff6b6b; }}
        .summary {{ background: #16213e; padding: 20px; border-radius: 8px; margin: 20px 0; 
                   display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; text-align: center; }}
        .summary-value {{ font-size: 2em; font-weight: bold; color: #00d4ff; }}
        .summary-label {{ color: #888; }}
        .instructions {{ background: #0f3460; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        code {{ background: #16213e; padding: 2px 8px; border-radius: 4px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🎮 Mali Batch Analysis Report</h1>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="summary">
        <div>
            <div class="summary-value">{len(results)}</div>
            <div class="summary-label">Total RDC Files</div>
        </div>
        <div>
            <div class="summary-value">{sum(1 for r in results if r.get("status") == "completed")}</div>
            <div class="summary-label">Completed</div>
        </div>
        <div>
            <div class="summary-value">{sum(1 for r in results if r.get("status") == "pending_manual_analysis")}</div>
            <div class="summary-label">Pending</div>
        </div>
        <div>
            <div class="summary-value">{sum(r.get("file_size_mb", 0) for r in results):.1f} MB</div>
            <div class="summary-label">Total Size</div>
        </div>
    </div>
    
    <div class="instructions">
        <h3>📋 批量分析说明</h3>
        <p>由于 RenderDoc 的 Python API 限制，完整的 Shader 分析需要在 RenderDoc GUI 中执行：</p>
        <ol>
            <li>打开 RenderDoc 并加载 RDC 文件</li>
            <li>打开 Python Shell (<code>Window → Python Shell</code>)</li>
            <li>复制运行 <code>renderdoc_mali_shell.py</code> 的内容</li>
            <li>执行 <code>analyze_current_capture()</code></li>
        </ol>
        <p>分析结果会自动保存到 <code>output/</code> 目录，支持历史对比。</p>
    </div>
    
    <h2>📁 RDC 文件列表</h2>
    <table>
        <tr>
            <th>文件名</th>
            <th>大小</th>
            <th>目标 GPU</th>
            <th>状态</th>
            <th>操作</th>
        </tr>
'''
    
    for r in results:
        status_class = "status-pending"
        status_text = "待分析"
        
        if r.get("status") == "completed":
            status_class = "status-ok"
            status_text = "✓ 已完成"
        elif r.get("status") == "error":
            status_class = "status-error"
            status_text = "✗ 错误"
        
        html += f'''
        <tr>
            <td>{r.get("rdc_name", "Unknown")}</td>
            <td>{r.get("file_size_mb", 0):.2f} MB</td>
            <td>{r.get("target_gpu", "-")}</td>
            <td class="{status_class}">{status_text}</td>
            <td><button onclick="copyPath('{r.get("rdc_file", "")}')">复制路径</button></td>
        </tr>'''
    
    html += '''
    </table>
    
    <script>
    function copyPath(path) {
        navigator.clipboard.writeText(path).then(() => {
            alert('路径已复制: ' + path);
        });
    }
    </script>
</div>
</body>
</html>'''
    
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    # 同时保存 JSON
    json_path = output_dir / f"batch_report_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "files": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Batch report generated:")
    print(f"  HTML: {report_path}")
    print(f"  JSON: {json_path}")
    
    return report_path


def main():
    parser = argparse.ArgumentParser(
        description="Mali Shader Analyzer - Batch Processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  py -3 batch_analyze.py --dir "D:/captures/"
  py -3 batch_analyze.py --dir "D:/captures/" --gpu "Mali-G710"
  py -3 batch_analyze.py --files "a.rdc,b.rdc" --gpu "Mali-G78"
  py -3 batch_analyze.py --list-gpus
        """
    )
    
    parser.add_argument("--dir", "-d", type=str, help="包含 RDC 文件的目录")
    parser.add_argument("--files", "-f", type=str, help="逗号分隔的 RDC 文件路径")
    parser.add_argument("--gpu", "-g", type=str, default="Mali-G78", help="目标 GPU 型号")
    parser.add_argument("--output", "-o", type=str, default=str(DEFAULT_OUTPUT_DIR), help="输出目录")
    parser.add_argument("--list-gpus", action="store_true", help="列出支持的 GPU")
    
    args = parser.parse_args()
    
    if args.list_gpus:
        print("\n支持的 Mali GPU 型号:")
        for gpu in SUPPORTED_GPUS:
            print(f"  - {gpu}")
        return
    
    if not args.dir and not args.files:
        parser.print_help()
        print("\n[ERROR] 请指定 --dir 或 --files 参数")
        sys.exit(1)
    
    # 验证 GPU
    if args.gpu not in SUPPORTED_GPUS:
        print(f"[WARNING] GPU '{args.gpu}' 可能不被支持")
        print(f"[INFO] 推荐使用: {', '.join(SUPPORTED_GPUS[:5])}")
    
    # 收集 RDC 文件
    rdc_files = []
    
    if args.dir:
        rdc_files.extend(find_rdc_files(args.dir))
    
    if args.files:
        for f in args.files.split(","):
            p = Path(f.strip())
            if p.exists():
                rdc_files.append(p)
            else:
                print(f"[WARNING] File not found: {f}")
    
    if not rdc_files:
        print("[ERROR] 未找到任何 RDC 文件")
        sys.exit(1)
    
    # 分析
    output_dir = Path(args.output)
    results = []
    
    for rdc_path in rdc_files:
        result = analyze_rdc_standalone(rdc_path, args.gpu, output_dir)
        if result:
            results.append(result)
    
    # 生成报告
    report_path = generate_batch_report(results, output_dir)
    
    print(f"\n✅ 批量处理完成")
    print(f"   共处理 {len(rdc_files)} 个文件")
    print(f"   报告路径: {report_path}")


if __name__ == "__main__":
    main()
