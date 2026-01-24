#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate RULES.md from code + thresholds config.

Data sources (single source of truth):
  - rules/*.py (RuleRegistry)
  - config/thresholds.py (get_thresholds)
"""

import argparse
import inspect
import textwrap
import ast
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_rule_threshold_calls(rule_class) -> List[Dict[str, Any]]:
    """Extract get_threshold(key, default) calls from a rule's check() method."""
    try:
        source = inspect.getsource(rule_class.check)
    except OSError:
        return []

    source = textwrap.dedent(source)
    tree = ast.parse(source)

    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "get_threshold":
            if not node.args:
                continue
            key_node = node.args[0]
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                key = key_node.value
            elif isinstance(key_node, ast.Str):
                key = key_node.s
            else:
                continue

            default = None
            if len(node.args) >= 2:
                default_node = node.args[1]
                if isinstance(default_node, ast.Constant):
                    default = default_node.value
                elif isinstance(default_node, ast.Num):
                    default = default_node.n
            calls.append({"key": key, "default": default})

    # 去重，保持顺序
    seen = set()
    unique = []
    for call in calls:
        if call["key"] in seen:
            continue
        seen.add(call["key"])
        unique.append(call)
    return unique


def _normalize_platforms(platforms: Optional[List[str]]) -> str:
    if not platforms:
        return "全平台"
    return ", ".join(platforms)


def _normalize_severity(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _normalize_category(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def collect_rules() -> List[Dict[str, Any]]:
    from rdc_analyzer.rules import RuleRegistry, register_all_rules
    from rdc_analyzer.config import get_thresholds

    register_all_rules()
    pc_thresholds = get_thresholds("pc")
    mobile_thresholds = get_thresholds("mobile")

    rules = []
    for rule_id, rule_cls in RuleRegistry.all().items():
        threshold_calls = _get_rule_threshold_calls(rule_cls)
        thresholds = []
        for call in threshold_calls:
            key = call["key"]
            default = call["default"]
            pc_value = pc_thresholds.get(key, default)
            mobile_value = mobile_thresholds.get(key, default)
            thresholds.append({
                "key": key,
                "pc": pc_value,
                "mobile": mobile_value,
                "default": default,
            })

        rules.append({
            "rule_id": rule_id,
            "name": getattr(rule_cls, "name", rule_id),
            "description": getattr(rule_cls, "description", ""),
            "severity": _normalize_severity(getattr(rule_cls, "severity", "")),
            "category": _normalize_category(getattr(rule_cls, "category", "")),
            "platforms": _normalize_platforms(getattr(rule_cls, "platforms", [])),
            "thresholds": thresholds,
        })

    # 按 category + rule_id 排序
    rules.sort(key=lambda r: (r["category"], r["rule_id"]))
    return rules


def _group_by_category(rules: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for rule in rules:
        grouped.setdefault(rule["category"], []).append(rule)
    return grouped


def render_markdown(rules: List[Dict[str, Any]]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    grouped = _group_by_category(rules)

    lines = []
    lines.append("# RDC Analyzer 规则文档")
    lines.append("")
    lines.append(f"> 自动生成于 {generated_at}，共 **{len(rules)} 条** 规则")
    lines.append("")
    lines.append("**数据来源**: rules/*.py + config/thresholds.py")
    lines.append("")
    lines.append("## 目录")
    lines.append("")

    for category, items in grouped.items():
        label = category.replace("_", " ").title()
        lines.append(f"- [{label} 规则](#{label.lower().replace(' ', '-')}-规则-{len(items)}-条)")
    lines.append("")
    lines.append("---")
    lines.append("")

    for category, items in grouped.items():
        label = category.replace("_", " ").title()
        lines.append(f"## {label} 规则 ({len(items)} 条)")
        lines.append("")
        for rule in items:
            lines.append(f"### {rule['rule_id']}: {rule['name']}")
            lines.append(f"- **严重程度**: {rule['severity']}")
            lines.append(f"- **平台**: {rule['platforms']}")
            if rule["description"]:
                lines.append(f"- **描述**: {rule['description']}")
            if rule["thresholds"]:
                lines.append("- **阈值**:")
                for th in rule["thresholds"]:
                    pc_val = th["pc"]
                    mobile_val = th["mobile"]
                    if pc_val == mobile_val:
                        lines.append(f"  - {th['key']}: {pc_val}")
                    else:
                        lines.append(f"  - {th['key']}: PC={pc_val}, Mobile={mobile_val}")
            else:
                lines.append("- **阈值**: 规则内部固定条件（无配置阈值）")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 规则配置")
    lines.append("")
    lines.append("阈值内置于 `scripts/rdc_analyzer/config/thresholds.py`。")
    lines.append("")
    lines.append("示例（仅展示部分键，实际以源码为准）：")
    lines.append("```python")
    lines.append("DEFAULT_THRESHOLDS = {")
    lines.append("  \"max_draw_calls\": 3000,")
    lines.append("  \"large_texture_threshold_mb\": 16.0,")
    lines.append("  \"max_pass_count\": 30,")
    lines.append("}")
    lines.append("MOBILE_THRESHOLDS = {")
    lines.append("  **DEFAULT_THRESHOLDS,")
    lines.append("  \"max_draw_calls\": 500,")
    lines.append("  \"large_texture_threshold_mb\": 4.0,")
    lines.append("  \"max_pass_count\": 15,")
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append("*Generated by rdc_analyzer script*")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate RULES.md from code.")
    parser.add_argument("--write", action="store_true", help="Write to RULES.md")
    parser.add_argument("--output", default="scripts/rdc_analyzer/RULES.md", help="Output path")
    args = parser.parse_args()

    rules = collect_rules()
    content = render_markdown(rules)

    if args.write:
        output_path = Path(args.output)
        output_path.write_text(content, encoding="utf-8")
        print(f"[+] Wrote {output_path}")
    else:
        print(content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
