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
            custom_thresholds=custom_thresholds
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