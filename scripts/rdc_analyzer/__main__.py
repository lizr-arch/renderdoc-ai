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

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="RDC 文件分析器 - 检测图形性能问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令:
  analyze   分析 RDC 文件并生成报告
  rules     列出或管理分析规则

示例:
  %(prog)s analyze capture.rdc
  %(prog)s analyze capture.rdc -o ./output --format html,json
  %(prog)s analyze capture.rdc --sample-textures --sample-buffers
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