#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC 对比分析工具
================

对比两个 RDC 捕获（或其 JSON 导出）的差异，生成回归分析报告。

用法:
    python compare_rdc.py <baseline> <target> [options]

示例:
    # 对比两个 JSON 导出
    python compare_rdc.py baseline.json target.json --html report.html
    
    # 同时生成 JSON 差异文件
    python compare_rdc.py baseline.json target.json --html report.html --json diff.json
    
    # 自定义回归阈值
    python compare_rdc.py baseline.json target.json --html report.html --triangle-threshold 0.1

Author: RenderDoc Analyzer Project
Version: 1.0.0
"""

import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from diff import (
    DiffEngine,
    DiffResult,
    RegressionDetector,
    RegressionReport,
    RegressionRuleId,
    DiffHTMLExporter,
    DiffHTMLConfig,
)
from parsers.rdc_loader import load_capture_file


def _estimate_bytes_per_pixel(format_name: str) -> int:
    """根据纹理格式名称估算每像素字节数
    
    Args:
        format_name: 纹理格式名称 (如 "R8G8B8A8_UNORM", "BC1_UNORM", etc.)
        
    Returns:
        每像素字节数估算值
    """
    fmt = format_name.upper()
    
    # 压缩格式 (BC/DXT/ASTC) - 返回平均每像素字节数
    if "BC1" in fmt or "DXT1" in fmt:
        return 0.5  # 4x4 block = 8 bytes = 0.5 bytes/pixel
    if "BC2" in fmt or "BC3" in fmt or "DXT3" in fmt or "DXT5" in fmt:
        return 1  # 4x4 block = 16 bytes = 1 byte/pixel
    if "BC4" in fmt:
        return 0.5
    if "BC5" in fmt:
        return 1
    if "BC6" in fmt or "BC7" in fmt:
        return 1
    if "ASTC" in fmt:
        # ASTC 块大小可变，假设 4x4
        return 1
    if "ETC" in fmt or "EAC" in fmt:
        return 0.5
    
    # 非压缩格式
    if "R32G32B32A32" in fmt:
        return 16
    if "R32G32B32" in fmt:
        return 12
    if "R32G32" in fmt:
        return 8
    if "R32" in fmt:
        return 4
    if "R16G16B16A16" in fmt:
        return 8
    if "R16G16B16" in fmt:
        return 6
    if "R16G16" in fmt:
        return 4
    if "R16" in fmt:
        return 2
    if "R8G8B8A8" in fmt or "B8G8R8A8" in fmt:
        return 4
    if "R8G8B8" in fmt or "B8G8R8" in fmt:
        return 3
    if "R8G8" in fmt:
        return 2
    if "R8" in fmt or "A8" in fmt:
        return 1
    if "R10G10B10A2" in fmt:
        return 4
    if "R11G11B10" in fmt:
        return 4
    if "D32" in fmt:
        return 4
    if "D24" in fmt:
        return 4  # D24 通常是 D24S8 = 4 bytes
    if "D16" in fmt:
        return 2
    if "S8" in fmt:
        return 1
    
    # 默认假设 4 字节/像素 (RGBA8)
    return 4


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Load JSON file.

    Only Canonical Schema dict format is accepted:
    {summary, textures, shaders, buffers, draw_calls}

    Args:
        file_path: JSON file path.

    Returns:
        Parsed JSON data as dict.

    Raises:
        FileNotFoundError: File not found.
        json.JSONDecodeError: JSON parse error.
        ValueError: Invalid top-level JSON type.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Phase 1 列表格式已弃用：强制拒绝
    if isinstance(data, list):
        raise ValueError("Phase1 列表格式已弃用，请使用 Canonical Schema (dict) 输入")
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是 dict (Canonical Schema)")
    
    # 已经是字典格式，直接返回
    return data


def run_comparison(
    baseline_data: Dict[str, Any],
    target_data: Dict[str, Any],
    baseline_name: str,
    target_name: str,
    custom_thresholds: Optional[Dict[RegressionRuleId, float]] = None,
    align_strategy: str = "signature"
) -> tuple:
    """执行对比分析
    
    Args:
        baseline_data: 基准 JSON 数据
        target_data: 目标 JSON 数据
        baseline_name: 基准文件名
        target_name: 目标文件名
        custom_thresholds: 自定义阈值配置
        align_strategy: DrawCall 对齐策略 ("order", "signature", "marker")
        
    Returns:
        (DiffResult, RegressionReport) 元组
    """
    # Step 1: 计算差异
    engine = DiffEngine(align_strategy=align_strategy)
    diff_result = engine.compare(baseline_data, target_data)
    
    # 更新文件名信息
    diff_result.baseline_file = baseline_name
    diff_result.target_file = target_name
    
    # Step 2: 检测回归
    detector = RegressionDetector(custom_thresholds=custom_thresholds)
    regression_report = detector.detect(diff_result)
    
    return diff_result, regression_report


def export_html_report(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    output_path: str,
    config: Optional[DiffHTMLConfig] = None
) -> str:
    """导出 HTML 报告
    
    Args:
        diff_result: 差异结果
        regression_report: 回归检测报告
        output_path: 输出文件路径
        config: HTML 导出配置
        
    Returns:
        实际输出的文件路径
    """
    exporter = DiffHTMLExporter(config or DiffHTMLConfig())
    html_content = exporter.export(diff_result, regression_report)
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return str(output)


def export_json_diff(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    output_path: str
) -> str:
    """导出 JSON 差异文件
    
    Args:
        diff_result: 差异结果
        regression_report: 回归检测报告
        output_path: 输出文件路径
        
    Returns:
        实际输出的文件路径
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # 构建输出结构
    data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "baseline_file": diff_result.baseline_file,
            "target_file": diff_result.target_file,
            "tool_version": "1.0.0"
        },
        "summary": {
            "draw_calls": {
                "baseline": diff_result.summary.draw_calls.baseline,
                "target": diff_result.summary.draw_calls.target,
                "delta": diff_result.summary.draw_calls.delta,
                "delta_percent": diff_result.summary.draw_calls.delta_percent
            },
            "triangles": {
                "baseline": diff_result.summary.triangles.baseline,
                "target": diff_result.summary.triangles.target,
                "delta": diff_result.summary.triangles.delta,
                "delta_percent": diff_result.summary.triangles.delta_percent
            },
            "vertices": {
                "baseline": diff_result.summary.vertices.baseline,
                "target": diff_result.summary.vertices.target,
                "delta": diff_result.summary.vertices.delta,
                "delta_percent": diff_result.summary.vertices.delta_percent
            },
            "texture_memory_bytes": {
                "baseline": diff_result.summary.texture_memory.baseline,
                "target": diff_result.summary.texture_memory.target,
                "delta": diff_result.summary.texture_memory.delta,
                "delta_percent": diff_result.summary.texture_memory.delta_percent
            },
            "buffer_memory_bytes": {
                "baseline": diff_result.summary.buffer_memory.baseline,
                "target": diff_result.summary.buffer_memory.target,
                "delta": diff_result.summary.buffer_memory.delta,
                "delta_percent": diff_result.summary.buffer_memory.delta_percent
            }
        },
        "regressions": {
            "has_critical": regression_report.has_critical,
            "has_warning": regression_report.has_warning,
            "issues": [
                {
                    "rule_id": issue.rule_id.value if hasattr(issue.rule_id, 'value') else str(issue.rule_id),
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "baseline_value": issue.baseline_value,
                    "target_value": issue.target_value,
                    "delta_percent": issue.delta_percent,
                    "affected_resources": issue.affected_resources,
                    "evidence": [
                        {
                            "event_id": e.event_id,
                            "marker_path": e.marker_path,
                            "description": e.description
                        }
                        for e in issue.evidence
                    ] if issue.evidence else []
                }
                for issue in regression_report.issues
            ]
        },
        "resource_changes": {
            "textures": {
                "added": diff_result.textures_added,
                "removed": diff_result.textures_removed,
                "modified": diff_result.textures_modified
            },
            "shaders": {
                "added": diff_result.shaders_added,
                "removed": diff_result.shaders_removed,
                "modified": diff_result.shaders_modified
            },
            "buffers": {
                "added": len([b for b in diff_result.buffer_diffs if b.status.value == "added"]),
                "removed": len([b for b in diff_result.buffer_diffs if b.status.value == "removed"]),
                "modified": len([b for b in diff_result.buffer_diffs if b.status.value == "modified"])
            },
            "draw_calls": {
                "added": diff_result.draw_calls_added,
                "removed": diff_result.draw_calls_removed,
                "modified": len([d for d in diff_result.draw_call_diffs if d.status.value == "modified"])
            }
        }
    }
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return str(output)


def print_summary(diff_result: DiffResult, regression_report: RegressionReport) -> None:
    """打印控制台摘要"""
    print()
    print("=" * 60)
    print("RDC 对比分析结果")
    print("=" * 60)
    print()
    
    # 文件信息
    print(f"  基准文件: {diff_result.baseline_file}")
    print(f"  目标文件: {diff_result.target_file}")
    print()
    
    # 指标变化
    print("指标变化:")
    print("-" * 40)
    
    metrics = [
        ("Draw Calls", diff_result.summary.draw_calls),
        ("三角形", diff_result.summary.triangles),
        ("顶点", diff_result.summary.vertices),
        ("纹理内存", diff_result.summary.texture_memory),
        ("Buffer 内存", diff_result.summary.buffer_memory),
    ]
    
    for name, m in metrics:
        delta_str = f"{m.delta:+.0f}" if m.delta != 0 else "0"
        pct_str = f"({m.delta_percent:+.1f}%)" if m.delta != 0 else ""
        
        # 对内存字段格式化为 MB
        if "内存" in name:
            base_str = f"{m.baseline / 1024 / 1024:.1f} MB"
            tgt_str = f"{m.target / 1024 / 1024:.1f} MB"
            delta_str = f"{m.delta / 1024 / 1024:+.2f} MB"
        else:
            base_str = f"{int(m.baseline):,}"
            tgt_str = f"{int(m.target):,}"
            delta_str = f"{int(m.delta):+,}"
        
        print(f"  {name:12s}: {base_str} → {tgt_str}  [{delta_str} {pct_str}]")
    
    print()
    
    # 资源变化
    print("资源变化:")
    print("-" * 40)
    
    # 使用 DiffResult 的属性统计
    resources = [
        ("纹理", diff_result.textures_added, diff_result.textures_removed, diff_result.textures_modified),
        ("Shaders", diff_result.shaders_added, diff_result.shaders_removed, diff_result.shaders_modified),
        ("Buffers", 
         len([b for b in diff_result.buffer_diffs if b.status.value == "added"]),
         len([b for b in diff_result.buffer_diffs if b.status.value == "removed"]),
         len([b for b in diff_result.buffer_diffs if b.status.value == "modified"])),
        ("Draw Calls", diff_result.draw_calls_added, diff_result.draw_calls_removed,
         len([d for d in diff_result.draw_call_diffs if d.status.value == "modified"])),
    ]
    
    for name, added, removed, modified in resources:
        total_changes = added + removed + modified
        if total_changes > 0:
            print(f"  {name:12s}: +{added} 新增, -{removed} 移除, ~{modified} 修改")
        else:
            print(f"  {name:12s}: 无变化")
    
    print()
    
    # 回归检测
    print("回归检测:")
    print("-" * 40)
    
    if not regression_report.issues:
        print("  ✓ 未检测到性能回归问题")
    else:
        critical = [i for i in regression_report.issues if i.severity.value == "critical"]
        warnings = [i for i in regression_report.issues if i.severity.value == "warning"]
        infos = [i for i in regression_report.issues if i.severity.value == "info"]
        
        if critical:
            print(f"\n  [!!!] 严重问题 ({len(critical)}):")
            for issue in critical:
                rule_id = issue.rule_id.value if hasattr(issue.rule_id, 'value') else str(issue.rule_id)
                print(f"    - [{rule_id}] {issue.message}")
        
        if warnings:
            print(f"\n  [!] 警告 ({len(warnings)}):")
            for issue in warnings[:5]:
                rule_id = issue.rule_id.value if hasattr(issue.rule_id, 'value') else str(issue.rule_id)
                print(f"    - [{rule_id}] {issue.message}")
            if len(warnings) > 5:
                print(f"    ... 还有 {len(warnings) - 5} 个警告")
        
        if infos:
            print(f"\n  [i] 提示 ({len(infos)}):")
            for issue in infos[:3]:
                rule_id = issue.rule_id.value if hasattr(issue.rule_id, 'value') else str(issue.rule_id)
                print(f"    - [{rule_id}] {issue.message}")
            if len(infos) > 3:
                print(f"    ... 还有 {len(infos) - 3} 个提示")
    
    print()


def main() -> int:
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="RDC 对比分析工具 - 检测两个捕获之间的差异和回归",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s baseline.json target.json --html report.html
  %(prog)s baseline.json target.json --html report.html --json diff.json
  %(prog)s baseline.json target.json --triangle-threshold 0.1

回归阈值说明:
  --triangle-threshold 0.2   三角形增加超过 20%% 时警告
  --draw-call-threshold 0.1  Draw Call 增加超过 10%% 时警告
  --texture-mem-threshold 0.3 纹理内存增加超过 30%% 时警告
        """
    )
    
    # 必需参数
    parser.add_argument(
        "baseline",
        help="基准文件 (JSON 格式)"
    )
    
    parser.add_argument(
        "target",
        help="目标文件 (JSON 格式)"
    )
    
    # 输出选项
    parser.add_argument(
        "--html", "-o",
        dest="html_output",
        help="输出 HTML 报告路径"
    )
    
    parser.add_argument(
        "--json", "-j",
        dest="json_output",
        help="输出 JSON 差异文件路径"
    )
    
    # 回归阈值选项
    parser.add_argument(
        "--triangle-threshold",
        type=float,
        default=0.2,
        help="三角形增加阈值 (默认: 0.2 = 20%%)"
    )
    
    parser.add_argument(
        "--draw-call-threshold",
        type=float,
        default=0.1,
        help="Draw Call 增加阈值 (默认: 0.1 = 10%%)"
    )
    
    parser.add_argument(
        "--texture-mem-threshold",
        type=float,
        default=0.3,
        help="纹理内存增加阈值 (默认: 0.3 = 30%%)"
    )
    
    parser.add_argument(
        "--buffer-mem-threshold",
        type=float,
        default=0.3,
        help="Buffer 内存增加阈值 (默认: 0.3 = 30%%)"
    )
    
    # 显示选项
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="静默模式，不打印控制台摘要"
    )
    
    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="HTML 报告主题 (默认: dark)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="RDC Compare Tool 1.0.0"
    )
    
    args = parser.parse_args()
    
    # 验证至少有一个输出
    if not args.html_output and not args.json_output and args.quiet:
        print("[!] 错误: 静默模式下至少需要指定一个输出 (--html 或 --json)")
        return 1
    
    try:
        # Step 1: 加载数据
        if not args.quiet:
            print(f"[*] 加载基准文件: {args.baseline}")
        baseline_data = load_capture_file(args.baseline, verbose=not args.quiet)
        
        if not args.quiet:
            print(f"[*] 加载目标文件: {args.target}")
        target_data = load_capture_file(args.target, verbose=not args.quiet)
        
        # Step 2: 配置回归阈值
        # REG001: Draw Call 增加, REG004: Buffer 增加, REG005: 三角形增加
        custom_thresholds = {
            RegressionRuleId.REG001: args.draw_call_threshold * 100,      # Draw Call 增加
            RegressionRuleId.REG004: args.buffer_mem_threshold * 100,     # Buffer 大小增加
            RegressionRuleId.REG005: args.triangle_threshold * 100,       # 三角形增加
        }
        
        # Step 3: 执行对比
        if not args.quiet:
            print("[*] 执行对比分析...")
        
        diff_result, regression_report = run_comparison(
            baseline_data=baseline_data,
            target_data=target_data,
            baseline_name=Path(args.baseline).name,
            target_name=Path(args.target).name,
            custom_thresholds=custom_thresholds
        )
        
        # Step 4: 输出
        output_files = []
        
        if args.html_output:
            html_config = DiffHTMLConfig(
                theme=args.theme
            )
            html_path = export_html_report(diff_result, regression_report, args.html_output, html_config)
            output_files.append(html_path)
            if not args.quiet:
                print(f"[+] HTML 报告: {html_path}")
        
        if args.json_output:
            json_path = export_json_diff(diff_result, regression_report, args.json_output)
            output_files.append(json_path)
            if not args.quiet:
                print(f"[+] JSON 差异: {json_path}")
        
        # Step 5: 打印摘要
        if not args.quiet:
            print_summary(diff_result, regression_report)
        
        # 返回值：有严重问题时返回 2，有警告时返回 1，否则返回 0
        if regression_report.has_critical:
            return 2
        elif regression_report.has_warning:
            return 1
        else:
            return 0
        
    except FileNotFoundError as e:
        print(f"[!] 错误: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"[!] JSON 解析错误: {e}")
        return 1
    except ValueError as e:
        print(f"[!] 输入错误: {e}")
        return 1
    except Exception as e:
        print(f"[!] 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
