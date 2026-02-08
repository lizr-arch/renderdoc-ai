#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Analyzer - 命令行入口
=========================

使用方式:
    python -m rdc_analyzer analyze <rdc_file> [options]
    python -m rdc_analyzer rules --list
    
示例:
    python -m rdc_analyzer analyze capture.rdc
    python -m rdc_analyzer analyze capture.rdc -o ./output --format html,json
    python -m rdc_analyzer analyze capture.rdc --platform mobile
    python -m rdc_analyzer rules --list
"""

import argparse
import sys
import os
from pathlib import Path

# 支持 `python -m rdc_analyzer` 和直接执行
if __name__ == "__main__" and __package__ is None:
    # 直接执行时设置包上下文
    _script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(_script_dir.parent))
    __package__ = "rdc_analyzer"

from .pipeline import analyze_rdc
from .rules import RuleRegistry, register_all_rules
from .parsers.rdc_loader import load_capture_file

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="RDC 文件分析器 - 检测图形性能问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令:
  analyze   分析 RDC 文件并生成报告
  compare   对比两个 RDC/JSON 文件并生成回归报告
  audit     资产审计 (单帧资源检查，无需对比基准)
  rules     列出或管理分析规则

示例:
  %(prog)s analyze capture.rdc
  %(prog)s analyze capture.rdc -o ./output --format html,json
  %(prog)s compare baseline.json target.json -o diff_report.html
  %(prog)s rules --list
        """
    )

    parser.add_argument(
        "--version",
        action="version",
        version="RDC Analyzer 2.0.0"
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用子命令')
    
    # ========== analyze 子命令 ==========
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='分析 RDC 文件并生成报告',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s capture.rdc
  %(prog)s capture.rdc -o ./output
  %(prog)s capture.rdc --format html,json --sample-textures
        """
    )
    
    analyze_parser.add_argument(
        "rdc_file",
        help="RDC 文件路径"
    )
    
    analyze_parser.add_argument(
        "-o", "--output",
        default="./output",
        help="输出目录 (默认: ./output)"
    )
    
    analyze_parser.add_argument(
        "-f", "--format",
        default="html",
        help="输出格式，逗号分隔 (默认: html，可选: html,json)"
    )
    
    analyze_parser.add_argument(
        "-p", "--platform",
        choices=["pc", "mobile"],
        default="pc",
        help="目标平台 (默认: pc)"
    )

    analyze_parser.add_argument(
        "--enable-tile-analysis",
        action="store_true",
        help="启用 Tile-Based GPU 分析 (默认: 关闭)"
    )
    
    analyze_parser.add_argument(
        "--tile-gpu",
        default="Generic-Tile",
        help="目标 Tile GPU 型号 (默认: Generic-Tile)"
    )
    
    analyze_parser.add_argument(
        "--enable-adreno-analysis",
        action="store_true",
        help="启用 Adreno 分析 (默认: 关闭)"
    )
    
    analyze_parser.add_argument(
        "--adreno-mode",
        choices=["heuristic", "profiler", "auto"],
        default="heuristic",
        help="Adreno 分析模式 (默认: heuristic)"
    )
    
    analyze_parser.add_argument(
        "--adreno-profiler-path",
        default=None,
        help="Snapdragon Profiler CLI 路径（可选）"
    )
    
    analyze_parser.add_argument(
        "--sample-textures",
        action="store_true",
        default=True,
        help="采样纹理数据生成缩略图 (默认: 启用)"
    )
    
    analyze_parser.add_argument(
        "--no-sample-textures",
        action="store_true",
        help="禁用纹理采样"
    )
    
    analyze_parser.add_argument(
        "--sample-buffers",
        action="store_true",
        default=True,
        help="采样 Buffer 数据 (默认: 启用)"
    )
    
    analyze_parser.add_argument(
        "--no-sample-buffers",
        action="store_true",
        help="禁用 Buffer 采样"
    )
    
    analyze_parser.add_argument(
        "--max-texture-size",
        type=int,
        default=256,
        help="纹理缩略图最大尺寸 (默认: 256)"
    )
    
    analyze_parser.add_argument(
        "--event-range",
        help="事件 ID 范围，格式: start-end (如: 100-500)"
    )
    
    analyze_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    # ========== compare 子命令 ==========
    compare_parser = subparsers.add_parser(
        'compare',
        help='对比两个 RDC/JSON 文件并生成回归报告',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s baseline.json target.json
  %(prog)s baseline.json target.json -o diff_report.html
  %(prog)s baseline.json target.json --html report.html --json diff.json
  %(prog)s baseline.rdc target.rdc -o ./compare_output

回归阈值说明:
  --triangle-threshold 0.2   三角形增加超过 20%% 时警告
  --draw-call-threshold 0.1  Draw Call 增加超过 10%% 时警告
  --texture-mem-threshold 0.3 纹理内存增加超过 30%% 时警告
        """
    )
    
    compare_parser.add_argument(
        "baseline",
        help="基准文件 (RDC 或 JSON 格式)"
    )
    
    compare_parser.add_argument(
        "target",
        help="目标文件 (RDC 或 JSON 格式)"
    )
    
    compare_parser.add_argument(
        "-o", "--output",
        default="./compare_output",
        help="输出目录或 HTML 文件路径 (默认: ./compare_output)"
    )
    
    compare_parser.add_argument(
        "--html",
        dest="html_output",
        help="指定 HTML 报告输出路径"
    )
    
    compare_parser.add_argument(
        "--json",
        dest="json_output",
        help="指定 JSON 差异文件输出路径"
    )
    
    compare_parser.add_argument(
        "--triangle-threshold",
        type=float,
        default=0.2,
        help="三角形增加阈值 (默认: 0.2 = 20%%)"
    )
    
    compare_parser.add_argument(
        "--draw-call-threshold",
        type=float,
        default=0.1,
        help="Draw Call 增加阈值 (默认: 0.1 = 10%%)"
    )
    
    compare_parser.add_argument(
        "--texture-mem-threshold",
        type=float,
        default=0.3,
        help="纹理内存增加阈值 (默认: 0.3 = 30%%)"
    )
    
    compare_parser.add_argument(
        "--buffer-mem-threshold",
        type=float,
        default=0.3,
        help="Buffer 内存增加阈值 (默认: 0.3 = 30%%)"
    )
    
    compare_parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="HTML 报告主题 (默认: dark)"
    )
    
    compare_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="静默模式，不打印控制台摘要"
    )
    
    compare_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    # 多帧统计采样参数
    compare_parser.add_argument(
        "--samples",
        type=int,
        default=1,
        metavar="N",
        help="采样帧数 (默认: 1，即单帧对比；N>1 时启用多帧统计对比)"
    )
    
    compare_parser.add_argument(
        "--baseline-dir",
        dest="baseline_dir",
        help="基准样本目录 (多帧模式，与 --samples 配合)"
    )
    
    compare_parser.add_argument(
        "--target-dir",
        dest="target_dir",
        help="目标样本目录 (多帧模式，与 --samples 配合)"
    )
    
    compare_parser.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
        choices=[0.90, 0.95, 0.99],
        help="置信水平 (默认: 0.95，可选: 0.90, 0.95, 0.99)"
    )
    
    # CI 集成参数
    compare_parser.add_argument(
        "--junit-xml",
        dest="junit_xml",
        metavar="FILE",
        help="输出 JUnit XML 报告 (供 CI 系统使用)"
    )
    
    compare_parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="检测到回归时返回非零退出码 (CI 模式)"
    )
    
    compare_parser.add_argument(
        "--fail-threshold",
        choices=["low", "medium", "high", "critical"],
        default="medium",
        help="触发失败的最低回归级别 (默认: medium)"
    )
    
    compare_parser.add_argument(
        "--align-strategy",
        choices=["order", "signature", "marker"],
        default="signature",
        help="DrawCall 对齐策略 (默认: signature，推荐: marker)"
    )
    
    # ========== audit 子命令 ==========
    audit_parser = subparsers.add_parser(
        'audit',
        help='资产审计 (单帧资源检查，无需对比基准)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s capture.json
  %(prog)s capture.json -o audit_report.html
  %(prog)s capture.json --preset mobile
  %(prog)s capture.rdc --platform mobile --output audit.html

预设说明:
  default   默认配置 (2048 纹理上限, 16MB 纹理内存)
  pc        PC 配置 (4096 纹理上限, 32MB 纹理内存)
  mobile    移动端配置 (2048 纹理上限, 8MB 内存, 检查 NPOT)
  strict    严格模式 (1024 纹理上限, 4MB 内存)
        """
    )
    
    audit_parser.add_argument(
        "input_file",
        help="输入文件 (RDC, XML 或 JSON 格式)"
    )
    
    audit_parser.add_argument(
        "-o", "--output",
        default="./audit_output",
        help="输出目录或文件路径 (默认: ./audit_output)"
    )
    
    audit_parser.add_argument(
        "-f", "--format",
        default="html",
        choices=["html", "json", "both"],
        help="输出格式 (默认: html)"
    )
    
    audit_parser.add_argument(
        "-p", "--platform",
        choices=["pc", "mobile"],
        default="pc",
        help="目标平台 (默认: pc)"
    )
    
    audit_parser.add_argument(
        "--preset",
        choices=["default", "pc", "mobile", "strict"],
        help="使用预设配置 (覆盖 --platform 推断)"
    )
    
    audit_parser.add_argument(
        "--max-texture-size",
        type=int,
        help="纹理最大尺寸阈值 (覆盖预设)"
    )
    
    audit_parser.add_argument(
        "--max-texture-memory",
        type=float,
        metavar="MB",
        help="单张纹理最大内存 (MB, 覆盖预设)"
    )
    
    audit_parser.add_argument(
        "--check-npot",
        action="store_true",
        help="检查非 2 次幂纹理"
    )
    
    audit_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="静默模式，不打印控制台摘要"
    )
    
    audit_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    audit_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="存在警告时返回非零退出码 (CI 模式)"
    )
    
    audit_parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="存在严重问题时返回非零退出码 (CI 模式)"
    )
    
    # ========== report 子命令 (新引擎) ==========
    report_parser = subparsers.add_parser(
        'report',
        help='使用新引擎生成 HTML 报告 (report_engine)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s capture.xml
  %(prog)s capture.xml -o report.html
  %(prog)s capture.xml --name "MyGame Frame 123"

说明:
  此命令使用新的 report_engine 模块生成 HTML 报告。
  支持从 XML 文件（由 renderdoccmd convert 生成）创建报告。
        """
    )
    
    report_parser.add_argument(
        "input_file",
        help="输入文件 (XML 格式，由 renderdoccmd convert -c xml 生成)"
    )
    
    report_parser.add_argument(
        "-o", "--output",
        help="输出 HTML 文件路径 (默认: <input>.html)"
    )
    
    report_parser.add_argument(
        "-n", "--name",
        help="报告标题/捕获名称 (默认: 使用文件名)"
    )
    
    report_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    # ========== bundle 子命令 (多页报告包) ==========
    bundle_parser = subparsers.add_parser(
        'bundle',
        help='生成多页 HTML 报告包 (index/events/textures/shaders)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s capture.json -o ./report_bundle
  %(prog)s capture.json -o ./report_bundle --external-data
  %(prog)s capture.json --validate

说明:
  此命令使用 report_bundle_generator 模块生成多页 HTML 报告包。
  输入文件为 JSON 格式（通过 analyze 命令或 XML 转换生成）。
  
  --external-data 参数会将大型数据数组外置为独立 JSON 文件，
  显著减少 HTML 文件大小，提升浏览器加载性能。
        """
    )
    
    bundle_parser.add_argument(
        "input_file",
        help="输入文件 (JSON 格式)"
    )
    
    bundle_parser.add_argument(
        "-o", "--output",
        default="./report_bundle",
        help="输出目录 (默认: ./report_bundle)"
    )
    
    bundle_parser.add_argument(
        "--external-data",
        action="store_true",
        dest="external_data",
        help="将数据外置为独立 JSON 文件，减少 HTML 大小 (推荐用于大型捕获)"
    )
    
    bundle_parser.add_argument(
        "--validate",
        action="store_true",
        help="启用 JSON Schema 验证"
    )
    
    bundle_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    # ========== extract-resources 子命令 ==========
    extract_parser = subparsers.add_parser(
        'extract-resources',
        help='从 RDC 文件提取资源 (纹理、Shader、RT 快照)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s capture.rdc -o ./resources
  %(prog)s capture.rdc --textures --shaders
  %(prog)s capture.rdc --rt-snapshots --draw-calls 100,200,300
  %(prog)s capture.rdc --all -o ./extracted

资源类型:
  --textures      导出所有纹理为 PNG
  --shaders       导出所有 Shader (HLSL/GLSL + ASM)
  --rt-snapshots  在指定 Draw Call 处导出 Render Target 快照
  --all           导出所有资源 (默认)
        """
    )
    
    extract_parser.add_argument(
        "rdc_file",
        help="RDC 文件路径"
    )
    
    extract_parser.add_argument(
        "-o", "--output",
        default="./extracted_resources",
        help="输出目录 (默认: ./extracted_resources)"
    )
    
    extract_parser.add_argument(
        "--textures",
        action="store_true",
        help="导出纹理"
    )
    
    extract_parser.add_argument(
        "--shaders",
        action="store_true",
        help="导出 Shader"
    )
    
    extract_parser.add_argument(
        "--rt-snapshots",
        action="store_true",
        dest="rt_snapshots",
        help="导出 Render Target 快照"
    )
    
    extract_parser.add_argument(
        "--all",
        action="store_true",
        dest="extract_all",
        help="导出所有资源类型 (默认行为)"
    )
    
    extract_parser.add_argument(
        "--draw-calls",
        dest="draw_calls",
        help="RT 快照的目标 Draw Call ID 列表 (逗号分隔，如: 100,200,300)"
    )
    
    extract_parser.add_argument(
        "--texture-max-size",
        type=int,
        default=0,
        dest="texture_max_size",
        help="纹理最大尺寸限制 (0=无限制，默认: 0)"
    )
    
    extract_parser.add_argument(
        "--texture-format",
        choices=["png", "jpg", "bmp", "tga", "hdr", "exr", "dds"],
        default="png",
        dest="texture_format",
        help="纹理输出格式 (默认: png)"
    )
    
    extract_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    # ========== rules 子命令 ==========
    rules_parser = subparsers.add_parser(
        'rules',
        help='列出或管理分析规则'
    )
    
    rules_parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="列出所有可用规则"
    )
    
    # ========== 兼容旧版：直接传入 rdc 文件 ==========
    # 如果第一个参数是 .rdc 文件，视为 analyze 命令
    if len(sys.argv) > 1 and sys.argv[1].endswith('.rdc'):
        sys.argv.insert(1, 'analyze')
    
    # 如果使用 --list-rules，转换为 rules --list
    if '--list-rules' in sys.argv:
        idx = sys.argv.index('--list-rules')
        sys.argv[idx] = 'rules'
        sys.argv.insert(idx + 1, '--list')
    
    args = parser.parse_args()
    
    # 处理子命令
    if args.command == 'analyze':
        return cmd_analyze(args)
    elif args.command == 'compare':
        return cmd_compare(args)
    elif args.command == 'audit':
        return cmd_audit(args)
    elif args.command == 'report':
        return cmd_report(args)
    elif args.command == 'bundle':
        return cmd_bundle(args)
    elif args.command == 'extract-resources':
        return cmd_extract_resources(args)
    elif args.command == 'rules':
        if args.list:
            return cmd_list_rules()
        else:
            rules_parser.print_help()
            return 0
    else:
        parser.print_help()
        return 0


def cmd_analyze(args):
    """执行分析命令"""
    # 检查文件存在
    if not os.path.exists(args.rdc_file):
        print(f"[!] 错误: 文件不存在: {args.rdc_file}")
        return 1
    
    # 解析输出格式
    output_formats = [f.strip() for f in args.format.split(',')]
    
    # 解析事件范围
    event_range = None
    if args.event_range:
        try:
            start, end = args.event_range.split('-')
            event_range = (int(start), int(end))
        except ValueError:
            print(f"[!] 错误: 无效的事件范围格式: {args.event_range}")
            print("    格式应为: start-end (如: 100-500)")
            return 1
    
    # 处理采样选项
    sample_textures = not args.no_sample_textures
    sample_buffers = not args.no_sample_buffers
    
    print(f"[*] 分析文件: {args.rdc_file}")
    print(f"[*] 输出目录: {args.output}")
    print(f"[*] 输出格式: {', '.join(output_formats)}")
    print(f"[*] 平台: {args.platform}")
    print(f"[*] 纹理采样: {'启用' if sample_textures else '禁用'}")
    print(f"[*] Buffer 采样: {'启用' if sample_buffers else '禁用'}")
    if event_range:
        print(f"[*] 事件范围: {event_range[0]} - {event_range[1]}")
    print()
    
    try:
        # 使用新的分析管线
        from .main import analyze, AnalysisOptions
        
        options = AnalysisOptions(
            output_formats=output_formats,
            output_dir=args.output,
            sample_textures=sample_textures,
            sample_buffers=sample_buffers,
            max_texture_size=args.max_texture_size,
            event_range=event_range,
            platform=args.platform,
            enable_tile_analysis=args.enable_tile_analysis,
            tile_gpu=args.tile_gpu,
            enable_adreno_analysis=args.enable_adreno_analysis,
            adreno_mode=args.adreno_mode,
            adreno_profiler_path=args.adreno_profiler_path,
            verbose=args.verbose,
            log_level='DEBUG' if args.verbose else 'INFO'
        )
        
        from .main import AnalysisPipeline
        pipeline = AnalysisPipeline(args.rdc_file, options)
        result = pipeline.run()
        
        # 打印摘要
        print()
        print("=" * 50)
        print("分析完成")
        print("=" * 50)
        print(f"  耗时:        {result.duration_seconds:.2f} 秒")
        print(f"  API:         {result.api}")
        print(f"  Draw Calls:  {result.draw_call_count}")
        print(f"  顶点数:      {result.total_vertices:,}")
        print(f"  纹理:        {result.texture_count}")
        print(f"  Buffer:      {result.buffer_count}")
        print()
        
        if result.warning_count > 0 or result.error_count > 0:
            print(f"  ⚠ 警告: {result.warning_count}")
            print(f"  ✗ 错误: {result.error_count}")
        else:
            print("  ✓ 未发现问题")
        
        print()
        print("输出文件:")
        for f in result.output_files:
            print(f"  → {f}")
        
        return 0
        
    except ImportError as e:
        # 回退到旧版管线
        print(f"[!] 注意: 新管线不可用 ({e})，使用旧版分析...")
        
        result = analyze_rdc(
            rdc_path=args.rdc_file,
            platform=args.platform,
            use_api=True,
        )
        
        print_summary_legacy(result, verbose=args.verbose)
        return 0
        
    except Exception as e:
        print(f"[!] 分析失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_compare(args):
    """执行对比命令"""
    from datetime import datetime
    import json
    
    # 判断是否为多帧统计模式
    multi_frame_mode = args.samples > 1 or args.baseline_dir or args.target_dir
    
    if multi_frame_mode:
        return cmd_compare_multi_frame(args)
    
    # 单帧对比模式
    # 检查文件存在
    if not os.path.exists(args.baseline):
        print(f"[!] 错误: 基准文件不存在: {args.baseline}")
        return 1
    
    if not os.path.exists(args.target):
        print(f"[!] 错误: 目标文件不存在: {args.target}")
        return 1
    
    # 导入对比模块
    try:
        from .compare_rdc import (
            load_json_data,
            run_comparison,
            export_html_report,
            export_json_diff,
            print_summary,
        )
        from .diff import RegressionRuleId, DiffHTMLConfig
    except ImportError as e:
        print(f"[!] 错误: 无法导入对比模块: {e}")
        return 1
    
    # 确定输入文件类型和处理方式
    baseline_path = Path(args.baseline)
    target_path = Path(args.target)
    baseline_ext = baseline_path.suffix.lower()
    target_ext = target_path.suffix.lower()
    
    if not args.quiet:
        print(f"[*] 基准文件: {args.baseline} ({baseline_ext})")
        print(f"[*] 目标文件: {args.target} ({target_ext})")
    
    # 使用统一的 load_capture_file 加载任意格式 (.rdc, .xml, .json)
    try:
        if not args.quiet:
            print(f"[*] 加载基准文件 ({baseline_ext})...")
        baseline_data = load_capture_file(args.baseline, verbose=args.verbose)
        
        if not args.quiet:
            print(f"[*] 加载目标文件 ({target_ext})...")
        target_data = load_capture_file(args.target, verbose=args.verbose)
        
        # 配置回归阈值
        custom_thresholds = {
            RegressionRuleId.REG001: args.draw_call_threshold * 100,
            RegressionRuleId.REG004: args.buffer_mem_threshold * 100,
            RegressionRuleId.REG005: args.triangle_threshold * 100,
        }
        
        # 执行对比
        if not args.quiet:
            print("[*] 执行对比分析...")
        
        diff_result, regression_report = run_comparison(
            baseline_data=baseline_data,
            target_data=target_data,
            baseline_name=baseline_path.name,
            target_name=target_path.name,
            custom_thresholds=custom_thresholds,
            align_strategy=args.align_strategy
        )
        
        # 确定输出路径
        output_path = Path(args.output)
        html_output = args.html_output
        json_output = args.json_output
        
        # 如果 -o 指定的是 .html 文件，直接作为 HTML 输出
        if output_path.suffix.lower() == '.html':
            html_output = str(output_path)
        elif not html_output and not json_output:
            # 默认在输出目录生成 HTML
            output_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_output = str(output_path / f"compare_{timestamp}.html")
        
        # 输出报告
        output_files = []
        
        if html_output:
            html_config = DiffHTMLConfig(theme=args.theme)
            html_path = export_html_report(diff_result, regression_report, html_output, html_config)
            output_files.append(html_path)
            if not args.quiet:
                print(f"[+] HTML 报告: {html_path}")
        
        if json_output:
            json_path = export_json_diff(diff_result, regression_report, json_output)
            output_files.append(json_path)
            if not args.quiet:
                print(f"[+] JSON 差异: {json_path}")
        
        # JUnit XML 输出 (CI 集成)
        if args.junit_xml:
            from .diff import JUnitXMLExporter, export_junit_xml
            
            junit_path = export_junit_xml(
                diff_result,
                regression_report,
                args.junit_xml,
                suite_name="RDC Regression Tests"
            )
            output_files.append(junit_path)
            if not args.quiet:
                print(f"[+] JUnit XML: {junit_path}")
        
        # 打印摘要
        if not args.quiet:
            print_summary(diff_result, regression_report)
        
        # 返回值（CI 模式）
        if args.fail_on_regression:
            from .diff import JUnitXMLExporter, RegressionSeverity
            
            # 根据 --fail-threshold 确定失败条件
            threshold_map = {
                "low": [RegressionSeverity.LOW, RegressionSeverity.MEDIUM, 
                        RegressionSeverity.HIGH, RegressionSeverity.WARNING,
                        RegressionSeverity.CRITICAL],
                "medium": [RegressionSeverity.MEDIUM, RegressionSeverity.HIGH, 
                           RegressionSeverity.WARNING, RegressionSeverity.CRITICAL],
                "high": [RegressionSeverity.HIGH, RegressionSeverity.CRITICAL],
                "critical": [RegressionSeverity.CRITICAL],
            }
            fail_severities = threshold_map.get(args.fail_threshold, [RegressionSeverity.MEDIUM])
            
            # 检查是否有达到阈值的回归（同时检查 issues 和 results）
            has_failing_regression = (
                any(i.severity in fail_severities for i in regression_report.issues) or
                any(r.severity in fail_severities for r in regression_report.results)
            )
            
            if has_failing_regression:
                if not args.quiet:
                    print(f"\n[!] CI 模式: 检测到 {args.fail_threshold}+ 级别回归，返回非零退出码")
                return JUnitXMLExporter.EXIT_CRITICAL if regression_report.has_critical else JUnitXMLExporter.EXIT_WARNING
            else:
                return JUnitXMLExporter.EXIT_SUCCESS
        else:
            # 传统模式：根据回归情况返回
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
    except Exception as e:
        print(f"[!] 对比失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_compare_multi_frame(args):
    """执行多帧统计对比命令
    
    多帧模式下：
    1. 从 baseline_dir/target_dir 加载多个 JSON 样本
    2. 使用 MultiFrameSampler 聚合统计数据
    3. 使用 StatisticalSummary 执行显著性检测
    4. 输出统计对比报告
    """
    from datetime import datetime
    import json
    
    # 导入统计模块
    try:
        from .stats import (
            MultiFrameSampler,
            StatisticalSummary,
        )
    except ImportError as e:
        print(f"[!] 错误: 无法导入统计模块: {e}")
        return 1
    
    # 确定样本目录
    baseline_dir = args.baseline_dir or args.baseline
    target_dir = args.target_dir or args.target
    
    # 验证目录
    baseline_path = Path(baseline_dir)
    target_path = Path(target_dir)
    
    if not baseline_path.exists():
        print(f"[!] 错误: 基准目录不存在: {baseline_dir}")
        return 1
    
    if not target_path.exists():
        print(f"[!] 错误: 目标目录不存在: {target_dir}")
        return 1
    
    if not args.quiet:
        print(f"[*] 多帧统计对比模式")
        print(f"[*] 基准目录: {baseline_dir}")
        print(f"[*] 目标目录: {target_dir}")
        print(f"[*] 置信水平: {args.confidence_level * 100:.0f}%")
        print()
    
    try:
        # Step 1: 加载基准样本
        if not args.quiet:
            print("[*] 加载基准样本...")
        
        baseline_sampler = MultiFrameSampler()
        
        if baseline_path.is_dir():
            baseline_count = baseline_sampler.add_samples_from_directory(str(baseline_path))
        else:
            # 单文件模式，直接加载
            data = load_capture_file(str(baseline_path), verbose=args.verbose)
            baseline_sampler.add_sample_from_json(data, baseline_path.name)
            baseline_count = 1
        
        if baseline_count == 0:
            print(f"[!] 错误: 基准目录中没有有效的 JSON 样本")
            return 1
        
        if not args.quiet:
            print(f"    加载了 {baseline_count} 个基准样本")
        
        # Step 2: 加载目标样本
        if not args.quiet:
            print("[*] 加载目标样本...")
        
        target_sampler = MultiFrameSampler()
        
        if target_path.is_dir():
            target_count = target_sampler.add_samples_from_directory(str(target_path))
        else:
            data = load_capture_file(str(target_path), verbose=args.verbose)
            target_sampler.add_sample_from_json(data, target_path.name)
            target_count = 1
        
        if target_count == 0:
            print(f"[!] 错误: 目标目录中没有有效的 JSON 样本")
            return 1
        
        if not args.quiet:
            print(f"    加载了 {target_count} 个目标样本")
        
        # Step 3: 聚合统计
        if not args.quiet:
            print("[*] 聚合统计数据...")
        
        baseline_aggregated = baseline_sampler.aggregate()
        target_aggregated = target_sampler.aggregate()
        
        # Step 4: 显著性检测
        if not args.quiet:
            print("[*] 执行显著性检测...")
        
        summary = StatisticalSummary(confidence_level=args.confidence_level)
        comparison_result = summary.compare(baseline_aggregated, target_aggregated)
        
        # Step 5: 输出报告
        output_path = Path(args.output)
        output_files = []
        
        # 打印摘要
        if not args.quiet:
            print(summary.format_summary(comparison_result))
        
        # 生成 JSON 输出
        json_output = args.json_output
        if json_output or (not args.html_output and not args.quiet):
            if not json_output:
                output_path.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_output = str(output_path / f"stats_compare_{timestamp}.json")
            
            # 构建输出数据
            output_data = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "mode": "multi_frame_statistical",
                    "confidence_level": args.confidence_level,
                    "baseline_dir": str(baseline_dir),
                    "target_dir": str(target_dir),
                },
                "baseline": baseline_aggregated.to_dict(),
                "target": target_aggregated.to_dict(),
                "comparison": comparison_result.to_dict(),
                "stability": {
                    "baseline": baseline_sampler.get_stability_report(),
                    "target": target_sampler.get_stability_report(),
                },
            }
            
            json_path = Path(json_output)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            output_files.append(str(json_path))
            if not args.quiet:
                print(f"[+] JSON 统计报告: {json_path}")
        
        # JUnit XML 输出 (CI 集成)
        if args.junit_xml:
            try:
                from .stats.junit_reporter import JUnitReporter
                
                # 构建 JUnit 兼容的比较结果
                junit_data = {
                    'baseline_count': baseline_count,
                    'target_count': target_count,
                    'metrics': {},
                    'significance': {},
                    'baseline': {},
                    'target': {},
                }
                
                # 转换指标数据
                for metric_name, metric_result in comparison_result.metrics.items():
                    junit_data['metrics'][metric_name] = {
                        'baseline': metric_result.baseline_mean,
                        'target': metric_result.target_mean,
                        'change': metric_result.delta,
                        'change_pct': metric_result.delta_percent,
                    }
                    # 计算 p 值（从 z_score 估算）
                    import math
                    z = abs(metric_result.z_score) if not math.isinf(metric_result.z_score) else 10.0
                    # 使用近似公式 p ≈ 2 * (1 - Φ(z))，简化为阈值判断
                    p_value = 0.001 if z > 3.29 else (0.01 if z > 2.58 else (0.05 if z > 1.96 else (0.10 if z > 1.645 else 1.0)))
                    
                    junit_data['significance'][metric_name] = {
                        'level': metric_result.significance.name.lower() if metric_result.significance else 'none',
                        'z_score': metric_result.z_score if not math.isinf(metric_result.z_score) else 999.0,
                        'p_value': p_value,
                        'effect_size': metric_result.effect_size,
                    }
                
                # 转换基准/目标统计（使用 dataclass 属性）
                metric_attrs = ['draw_calls', 'vertices', 'triangles', 'texture_count', 
                               'texture_memory', 'buffer_count', 'buffer_memory', 'shader_count']
                
                for metric_name in metric_attrs:
                    baseline_stat = getattr(baseline_aggregated, metric_name, None)
                    if baseline_stat:
                        junit_data['baseline'][metric_name] = {
                            'mean': baseline_stat.mean,
                            'std': baseline_stat.std,
                        }
                
                for metric_name in metric_attrs:
                    target_stat = getattr(target_aggregated, metric_name, None)
                    if target_stat:
                        junit_data['target'][metric_name] = {
                            'mean': target_stat.mean,
                            'std': target_stat.std,
                        }
                
                reporter = JUnitReporter(
                    suite_name="RDC Multi-Frame Regression",
                    fail_threshold=args.fail_threshold,
                    confidence_level=args.confidence_level
                )
                junit_path = reporter.save(junit_data, args.junit_xml)
                output_files.append(str(junit_path))
                if not args.quiet:
                    print(f"[+] JUnit XML: {junit_path}")
            except Exception as e:
                print(f"[!] 警告: JUnit XML 生成失败: {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
        
        # 打印输出文件列表
        if output_files and not args.quiet:
            print()
            print("输出文件:")
            for f in output_files:
                print(f"  → {f}")
        
        # 返回值基于显著性检测结果
        if comparison_result.has_significant_regression:
            # 检查严重程度
            from .stats import SignificanceLevel
            high_sig = any(
                comparison_result.metrics[m].significance == SignificanceLevel.HIGH
                for m in comparison_result.significant_metrics
            )
            if high_sig:
                return 2  # 高显著性回归
            else:
                return 1  # 中/低显著性回归
        else:
            return 0
            
    except Exception as e:
        print(f"[!] 多帧对比失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_audit(args):
    """执行资产审计命令"""
    from datetime import datetime
    import json
    
    # 检查文件存在
    if not os.path.exists(args.input_file):
        print(f"[!] 错误: 文件不存在: {args.input_file}")
        return 1
    
    # 导入审计模块
    try:
        from .audit import AuditEngine, AuditReport
        from .audit.engine import AuditPreset, PRESETS
    except ImportError as e:
        print(f"[!] 错误: 无法导入审计模块: {e}")
        return 1
    
    input_path = Path(args.input_file)
    
    if not args.quiet:
        print(f"[*] 资产审计模式")
        print(f"[*] 输入文件: {args.input_file}")
        print(f"[*] 平台: {args.platform}")
        print(f"[*] 预设: {args.preset or 'auto'}")
    
    try:
        # Step 1: 加载捕获数据
        if not args.quiet:
            print(f"[*] 加载文件...")
        
        capture_data = load_capture_file(args.input_file, verbose=args.verbose)
        
        # Step 2: 创建审计引擎
        # 构建自定义配置 (如果有)
        custom_config = None
        if args.max_texture_size or args.max_texture_memory or args.check_npot:
            # 获取基础预设
            base_preset = PRESETS.get(args.preset or args.platform, PRESETS["default"])
            custom_config = AuditPreset(
                name=f"custom_{args.platform}",
                max_texture_size=args.max_texture_size or base_preset.max_texture_size,
                max_texture_memory_mb=args.max_texture_memory or base_preset.max_texture_memory_mb,
                require_mipmap_size=base_preset.require_mipmap_size,
                require_compression_size=base_preset.require_compression_size,
                max_buffer_size_mb=base_preset.max_buffer_size_mb,
                check_npot=args.check_npot or base_preset.check_npot,
                strict_mode=base_preset.strict_mode,
            )
        
        engine = AuditEngine(
            platform=args.platform,
            preset=args.preset,
            custom_config=custom_config,
        )
        
        if not args.quiet:
            print(f"[*] 使用预设: {engine.preset.name}")
            print(f"[*] 执行审计...")
        
        # Step 3: 执行审计
        report = engine.audit(capture_data, file_path=str(input_path))
        
        # Step 4: 输出报告
        output_path = Path(args.output)
        output_files = []
        
        # 确定输出格式
        output_html = args.format in ("html", "both")
        output_json = args.format in ("json", "both")
        
        # 如果 -o 指定的是 .html/.json 文件，直接作为输出
        if output_path.suffix.lower() == '.html':
            html_output_path = output_path
            output_html = True
        elif output_path.suffix.lower() == '.json':
            json_output_path = output_path
            output_json = True
        else:
            # 在输出目录生成文件
            output_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_output_path = output_path / f"audit_{timestamp}.html"
            json_output_path = output_path / f"audit_{timestamp}.json"
        
        # 输出 JSON
        if output_json:
            if 'json_output_path' not in locals():
                json_output_path = output_path / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            json_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            
            output_files.append(str(json_output_path))
            if not args.quiet:
                print(f"[+] JSON 报告: {json_output_path}")
        
        # 输出 HTML (简易版，后续可扩展模板)
        if output_html:
            if 'html_output_path' not in locals():
                html_output_path = output_path / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            html_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            html_content = _generate_audit_html(report)
            with open(html_output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            output_files.append(str(html_output_path))
            if not args.quiet:
                print(f"[+] HTML 报告: {html_output_path}")
        
        # 打印摘要
        if not args.quiet:
            print(report.format_summary())
        
        # 打印输出文件列表
        if output_files and not args.quiet:
            print("输出文件:")
            for f in output_files:
                print(f"  → {f}")
        
        # 返回值 (CI 模式)
        if args.fail_on_critical and report.has_critical:
            if not args.quiet:
                print(f"\n[!] CI 模式: 存在严重问题，返回非零退出码")
            return 2
        elif args.fail_on_warning and report.has_warning:
            if not args.quiet:
                print(f"\n[!] CI 模式: 存在警告，返回非零退出码")
            return 1
        else:
            return 0
            
    except FileNotFoundError as e:
        print(f"[!] 错误: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"[!] JSON 解析错误: {e}")
        return 1
    except Exception as e:
        print(f"[!] 审计失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def _generate_audit_html(report) -> str:
    """生成审计报告 HTML"""
    from .audit.report import AuditSeverity
    
    # 严重程度样式映射
    severity_colors = {
        AuditSeverity.CRITICAL: "#ff4444",
        AuditSeverity.WARNING: "#ffaa00",
        AuditSeverity.INFO: "#4488ff",
        AuditSeverity.PASS: "#44cc44",
    }
    
    severity_labels = {
        AuditSeverity.CRITICAL: "严重",
        AuditSeverity.WARNING: "警告",
        AuditSeverity.INFO: "提示",
        AuditSeverity.PASS: "通过",
    }
    
    # 构建问题列表 HTML
    issues_html = ""
    for issue in report.issues:
        color = severity_colors.get(issue.severity, "#888")
        label = severity_labels.get(issue.severity, str(issue.severity))
        issues_html += f"""
        <tr>
            <td style="color: {color}; font-weight: bold;">{label}</td>
            <td><code>{issue.rule_id}</code></td>
            <td>{issue.message}</td>
            <td>{issue.suggestion or '-'}</td>
        </tr>
        """
    
    if not issues_html:
        issues_html = '<tr><td colspan="4" style="text-align:center; color:#888;">未发现问题</td></tr>'
    
    # 纹理列表 HTML
    textures_html = ""
    for tex in report.textures[:50]:  # 限制前 50 个
        textures_html += f"""
        <tr>
            <td>{tex.get('name', tex.get('resource_id', '-'))}</td>
            <td>{tex.get('width', 0)}x{tex.get('height', 0)}</td>
            <td>{tex.get('format', '-')}</td>
            <td>{tex.get('mip_levels', 1)}</td>
            <td>{tex.get('memory_size', 0) / 1024:.1f} KB</td>
        </tr>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>资产审计报告 - {report.file_path}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; margin: 0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #4ecdc4; }}
        h2 {{ color: #88ccff; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        .grade {{ font-size: 48px; font-weight: bold; text-align: center; padding: 20px; border-radius: 10px; }}
        .grade-A {{ background: #22aa44; }}
        .grade-B {{ background: #88cc44; }}
        .grade-C {{ background: #ccaa44; }}
        .grade-D {{ background: #cc7744; }}
        .grade-F {{ background: #cc4444; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .summary-card {{ background: #252545; padding: 15px; border-radius: 8px; }}
        .summary-card h3 {{ margin: 0 0 10px 0; color: #aaa; font-size: 14px; }}
        .summary-card .value {{ font-size: 24px; font-weight: bold; color: #4ecdc4; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #252545; color: #aaa; }}
        tr:hover {{ background: #2a2a4a; }}
        code {{ background: #333; padding: 2px 6px; border-radius: 3px; }}
        .meta {{ color: #888; font-size: 12px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 资产审计报告</h1>
        <p class="meta">
            文件: {report.file_path} | 
            平台: {report.platform} | 
            预设: {report.preset} |
            时间: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}
        </p>
        
        <div class="grade grade-{report.summary.grade}">
            评级: {report.summary.grade}
        </div>
        
        <h2>📈 统计摘要</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <h3>严重问题</h3>
                <div class="value" style="color: #ff4444;">{report.summary.critical_count}</div>
            </div>
            <div class="summary-card">
                <h3>警告</h3>
                <div class="value" style="color: #ffaa00;">{report.summary.warning_count}</div>
            </div>
            <div class="summary-card">
                <h3>提示</h3>
                <div class="value" style="color: #4488ff;">{report.summary.info_count}</div>
            </div>
            <div class="summary-card">
                <h3>纹理数量</h3>
                <div class="value">{report.summary.texture_stats.count}</div>
            </div>
            <div class="summary-card">
                <h3>纹理内存</h3>
                <div class="value">{report.summary.texture_stats.total_memory / (1024*1024):.1f} MB</div>
            </div>
            <div class="summary-card">
                <h3>Buffer 数量</h3>
                <div class="value">{report.summary.buffer_stats.count}</div>
            </div>
            <div class="summary-card">
                <h3>Buffer 内存</h3>
                <div class="value">{report.summary.buffer_stats.total_memory / (1024*1024):.1f} MB</div>
            </div>
            <div class="summary-card">
                <h3>总资源内存</h3>
                <div class="value">{report.summary.total_memory / (1024*1024):.1f} MB</div>
            </div>
        </div>
        
        <h2>⚠️ 问题列表 ({report.summary.total_issues})</h2>
        <table>
            <thead>
                <tr>
                    <th>严重程度</th>
                    <th>规则</th>
                    <th>问题描述</th>
                    <th>建议</th>
                </tr>
            </thead>
            <tbody>
                {issues_html}
            </tbody>
        </table>
        
        <h2>🖼️ 纹理清单 (前 50 个)</h2>
        <table>
            <thead>
                <tr>
                    <th>名称</th>
                    <th>尺寸</th>
                    <th>格式</th>
                    <th>Mip 层级</th>
                    <th>内存</th>
                </tr>
            </thead>
            <tbody>
                {textures_html}
            </tbody>
        </table>
        
        <p class="meta" style="margin-top: 40px;">
            Generated by RDC Analyzer v2.0.0 | Audit Mode
        </p>
    </div>
</body>
</html>
"""
    return html


def _analyze_rdc_to_json(rdc_path: str, verbose: bool = False) -> Path:
    """分析 RDC 文件并返回 JSON 输出路径
    
    .. deprecated:: 2.0.0
        使用 `load_capture_file` 代替，它支持 .rdc, .xml, .json 格式统一加载。
    
    Args:
        rdc_path: RDC 文件路径
        verbose: 是否详细输出
        
    Returns:
        生成的 JSON 文件路径
    """
    import warnings
    warnings.warn(
        "_analyze_rdc_to_json 已弃用，请使用 load_capture_file 代替",
        DeprecationWarning,
        stacklevel=2
    )
    import tempfile
    from .main import AnalysisPipeline, AnalysisOptions
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="rdc_compare_"))
    
    options = AnalysisOptions(
        output_formats=['json'],
        output_dir=str(temp_dir),
        sample_textures=False,
        sample_buffers=False,
        verbose=verbose,
    )
    
    pipeline = AnalysisPipeline(rdc_path, options)
    result = pipeline.run()
    
    # 查找生成的 JSON 文件
    json_files = list(temp_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"未能生成 JSON 输出: {rdc_path}")
    
    return json_files[0]


def cmd_report(args):
    """使用新引擎生成 HTML 报告 (report_engine)"""
    # 检查文件存在
    if not os.path.exists(args.input_file):
        print(f"[!] 错误: 文件不存在: {args.input_file}")
        return 1
    
    input_path = Path(args.input_file)
    input_ext = input_path.suffix.lower()
    
    # 目前只支持 XML
    if input_ext != '.xml':
        print(f"[!] 错误: 目前 report 命令只支持 XML 文件")
        print(f"    输入文件格式: {input_ext}")
        print("    提示: 使用 renderdoccmd convert -c xml 生成 XML 文件")
        return 1
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.html')
    
    # 确定报告名称
    rdc_name = args.name or input_path.stem
    
    print(f"[*] 使用 report_engine 生成报告")
    print(f"[*] 输入: {args.input_file}")
    print(f"[*] 输出: {output_path}")
    print(f"[*] 名称: {rdc_name}")
    print()
    
    try:
        # 导入新引擎
        from .report_engine import XmlAdapter, HtmlRenderer
        
        # 加载 XML 并转换为数据契约
        print("[*] 解析 XML 文件...")
        adapter = XmlAdapter()
        contract = adapter.from_xml_file(str(input_path), rdc_name)
        
        if args.verbose:
            print(f"    纹理: {len(contract.textures)}")
            print(f"    Buffer: {len(contract.buffers)}")
            print(f"    Draw Calls: {len(contract.events)}")
        
        # 渲染 HTML
        print("[*] 生成 HTML 报告...")
        renderer = HtmlRenderer()
        html_path = renderer.render_to_file(contract, str(output_path), rdc_name)
        
        print()
        print("=" * 50)
        print("报告生成完成")
        print("=" * 50)
        print(f"  输出文件: {html_path}")
        print(f"  文件大小: {output_path.stat().st_size / 1024:.1f} KB")
        print()
        
        return 0
        
    except Exception as e:
        print(f"[!] 报告生成失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_bundle(args):
    """生成多页 HTML 报告包 (report_bundle_generator)"""
    import json
    
    # 检查文件存在
    if not os.path.exists(args.input_file):
        print(f"[!] 错误: 文件不存在: {args.input_file}")
        return 1
    
    input_path = Path(args.input_file)
    input_ext = input_path.suffix.lower()
    
    # 检查文件格式
    if input_ext != '.json':
        print(f"[!] 错误: 目前 bundle 命令只支持 JSON 文件")
        print(f"    输入文件格式: {input_ext}")
        print("    提示: 使用 analyze 命令或 XML 转换生成 JSON 文件")
        return 1
    
    output_dir = Path(args.output)
    
    print("=" * 60)
    print("RDC Analyzer - 生成报告包")
    print("=" * 60)
    print(f"  输入: {args.input_file}")
    print(f"  输出: {output_dir}")
    print(f"  外部数据: {'是' if args.external_data else '否'}")
    print(f"  Schema 验证: {'是' if args.validate else '否'}")
    print()
    
    try:
        # 导入报告生成器
        from .report_bundle_generator import generate_report_bundle
        
        # 加载 JSON 数据
        print("[*] 加载 JSON 数据...")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if args.verbose:
            events = data.get('events', data.get('draw_calls', []))
            textures = data.get('textures', [])
            shaders = data.get('shaders', [])
            print(f"    事件: {len(events)}")
            print(f"    纹理: {len(textures)}")
            print(f"    Shader: {len(shaders)}")
        
        # 生成报告包
        print("[*] 生成报告包...")
        
        # 从数据中提取各部分
        events = data.get('events', data.get('draw_calls', []))
        textures = data.get('textures', [])
        shaders = data.get('shaders', [])
        performance_data = data.get('performance', data.get('summary', None))
        mali_data = data.get('mali_data', None)
        
        output_files = generate_report_bundle(
            output_dir=str(output_dir),
            capture_name=input_path.stem,
            textures=textures,
            events=events,
            shaders=shaders,
            performance_data=performance_data,
            mali_data=mali_data,
            validate_schema=args.validate,
            external_data=args.external_data
        )
        
        print()
        print("=" * 60)
        print("报告包生成完成")
        print("=" * 60)
        print(f"  输出目录: {output_dir}")
        print(f"  文件数量: {len(output_files)}")
        
        if args.external_data:
            print()
            print("  [INFO] 外部数据模式已启用:")
            for key, filename in output_files.items():
                if key.endswith('_data'):
                    file_path = output_dir / filename
                    if file_path.exists():
                        size_kb = file_path.stat().st_size / 1024
                        print(f"    - {filename}: {size_kb:.1f} KB")
        
        print()
        print(f"  [INFO] 打开报告: {output_dir / 'index.html'}")
        print()
        
        return 0
        
    except Exception as e:
        print(f"[!] 报告生成失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_list_rules():
    """列出所有规则"""
    register_all_rules()
    
    print("=" * 60)
    print("RDC Analyzer - 可用规则")
    print("=" * 60)
    print()
    
    rules = RuleRegistry.all()
    
    # 按分类分组
    by_category = {}
    for rule_id, rule_class in rules.items():
        cat = rule_class.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(rule_class)
    
    for category, rule_list in sorted(by_category.items()):
        print(f"## {category}")
        print()
        for rule in sorted(rule_list, key=lambda r: r.rule_id):
            platforms = ", ".join(rule.platforms) if rule.platforms else "all"
            print(f"  [{rule.rule_id}] {rule.name}")
            print(f"      {rule.description}")
            print(f"      严重程度: {rule.severity}, 平台: {platforms}")
            print()
    
    print(f"共 {len(rules)} 条规则")
    return 0


def cmd_extract_resources(args):
    """执行资源提取命令"""
    from datetime import datetime
    
    # 检查文件存在
    if not os.path.exists(args.rdc_file):
        print(f"[!] 错误: 文件不存在: {args.rdc_file}")
        return 1
    
    # 导入资源提取模块
    try:
        from .extractors import (
            RdcResourceExtractor,
            ResourceExtractorConfig,
            extract_resources,
        )
    except ImportError as e:
        print(f"[!] 错误: 无法导入资源提取模块: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # 确定提取类型
    extract_textures = args.textures
    extract_shaders = args.shaders
    extract_rt = args.rt_snapshots
    
    # 如果都没指定或指定了 --all，则提取全部
    if args.extract_all or (not extract_textures and not extract_shaders and not extract_rt):
        extract_textures = True
        extract_shaders = True
        extract_rt = True
    
    # 解析 Draw Call 列表
    rt_draw_calls = None
    if args.draw_calls:
        try:
            rt_draw_calls = [int(x.strip()) for x in args.draw_calls.split(',')]
        except ValueError:
            print(f"[!] 错误: 无效的 Draw Call ID 格式: {args.draw_calls}")
            print("    格式应为逗号分隔的数字，如: 100,200,300")
            return 1
    
    # 映射纹理格式到 FileType (简化，实际可扩展)
    texture_format_map = {
        "png": "png",
        "jpg": "jpg",
        "bmp": "bmp",
        "tga": "tga",
        "hdr": "hdr",
        "exr": "exr",
        "dds": "dds",
    }
    
    print(f"[*] 资源提取模式")
    print(f"[*] RDC 文件: {args.rdc_file}")
    print(f"[*] 输出目录: {args.output}")
    print(f"[*] 提取类型:")
    print(f"    - 纹理: {'是' if extract_textures else '否'}")
    print(f"    - Shader: {'是' if extract_shaders else '否'}")
    print(f"    - RT 快照: {'是' if extract_rt else '否'}")
    if rt_draw_calls:
        print(f"    - RT Draw Calls: {rt_draw_calls}")
    print()
    
    try:
        # 执行提取（使用便捷函数接口）
        print("[*] 打开 RDC 文件...")
        result = extract_resources(
            rdc_path=args.rdc_file,
            output_dir=args.output,
            textures=extract_textures,
            shaders=extract_shaders,
            rt_snapshots=extract_rt,
            verbose=args.verbose
        )
        
        # 打印摘要
        print()
        print("=" * 50)
        print("资源提取完成")
        print("=" * 50)
        
        if result.textures_extracted > 0 or result.textures_skipped > 0:
            print(f"  纹理:        {result.textures_extracted} 个 (跳过 {result.textures_skipped}, 失败 {result.textures_failed})")
        if result.shaders_extracted > 0 or result.shaders_skipped > 0:
            print(f"  Shader:      {result.shaders_extracted} 个 (跳过 {result.shaders_skipped})")
        if result.rt_snapshots_extracted > 0 or result.rt_snapshots_failed > 0:
            print(f"  RT 快照:     {result.rt_snapshots_extracted} 个 (失败 {result.rt_snapshots_failed})")
        
        if result.errors:
            print()
            print(f"  ⚠ 错误: {len(result.errors)} 个")
            if args.verbose:
                for err in result.errors[:10]:
                    print(f"    - {err}")
                if len(result.errors) > 10:
                    print(f"    ... 还有 {len(result.errors) - 10} 个错误")
        
        if result.warnings:
            print()
            print(f"  ⚠ 警告: {len(result.warnings)} 个")
        
        print()
        print(f"输出目录: {args.output}")
        
        return 0 if not result.errors else 1
        
    except Exception as e:
        print(f"[!] 资源提取失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def print_summary_legacy(result, verbose: bool = False):
    """打印分析摘要（旧版兼容）"""
    s = result.frame_summary
    
    print("=" * 50)
    print("帧摘要")
    print("=" * 50)
    print(f"  Draw Call:    {s.draw_call_count}")
    print(f"  顶点数:       {s.vertex_count:,}")
    print(f"  纹理数:       {s.texture_count}")
    print(f"  Buffer 数:    {s.buffer_count}")
    print(f"  Pass 数:      {s.pass_count}")
    print()
    
    # 问题统计
    issues = result.issues
    if issues:
        print("=" * 50)
        print(f"检测问题 ({len(issues)})")
        print("=" * 50)
        
        # 按严重程度排序
        critical = [i for i in issues if i.severity == "critical"]
        warnings = [i for i in issues if i.severity == "warning"]
        info = [i for i in issues if i.severity == "info"]
        
        if critical:
            print("\n[!!!] 严重问题:")
            for issue in critical:
                print(f"  - [{issue.code}] {issue.message}")
        
        if warnings:
            print("\n[!] 警告:")
            for issue in warnings[:10]:
                print(f"  - [{issue.code}] {issue.message}")
            if len(warnings) > 10:
                print(f"  ... 还有 {len(warnings) - 10} 个警告")
        
        if verbose and info:
            print("\n[i] 提示:")
            for issue in info[:5]:
                print(f"  - [{issue.code}] {issue.message}")
            if len(info) > 5:
                print(f"  ... 还有 {len(info) - 5} 个提示")
    else:
        print("\n[+] 未发现问题！")


if __name__ == "__main__":
    sys.exit(main())
