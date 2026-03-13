#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC compare CLI
===============

Compare two RenderDoc captures or compatible JSON exports and produce
structured diff / CI outputs without creating a second reporting pipeline.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add module path for direct script execution.
sys.path.insert(0, str(Path(__file__).parent))

from diff import (
    DEFAULT_RULES,
    DiffEngine,
    DiffHTMLConfig,
    DiffHTMLExporter,
    DiffResult,
    JUnitXMLExporter,
    MetricDiff,
    RegressionDetector,
    RegressionIssue,
    RegressionReport,
    RegressionResult,
    RegressionRuleId,
    RegressionSeverity,
)
from parsers.rdc_loader import load_capture_file


TOOL_VERSION = "1.1.0"

WARNING_SEVERITIES = {
    RegressionSeverity.WARNING,
    RegressionSeverity.MEDIUM,
    RegressionSeverity.HIGH,
}

RULE_CATEGORY = {
    RegressionRuleId.REG001: "DrawCalls",
    RegressionRuleId.REG002: "Textures",
    RegressionRuleId.REG003: "Shaders",
    RegressionRuleId.REG004: "BufferMemory",
    RegressionRuleId.REG005: "Triangles",
    RegressionRuleId.REG006: "Overdraw",
    RegressionRuleId.REG007: "RenderPass",
}

RULE_METRIC_NAME = {
    RegressionRuleId.REG001: "draw_calls",
    RegressionRuleId.REG002: "texture_resolution",
    RegressionRuleId.REG003: "shader_changes",
    RegressionRuleId.REG004: "buffer_memory",
    RegressionRuleId.REG005: "triangles",
    RegressionRuleId.REG006: "overdraw",
    RegressionRuleId.REG007: "new_passes",
}

SNAPSHOT_COUNT_KEYS = (
    "actions",
    "draw_calls",
    "dispatch_calls",
    "triangles",
    "vertices",
    "textures",
    "buffers",
    "shaders",
    "passes",
    "pipelines",
    "findings",
    "recommendations",
)


@dataclass
class CIVerdict:
    status: str
    exit_code: int
    thresholds: Dict[str, float]
    failing_checks: List[str] = field(default_factory=list)
    summary_lines: List[str] = field(default_factory=list)
    results: List[RegressionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "thresholds": dict(self.thresholds),
            "failing_checks": list(self.failing_checks),
            "summary_lines": list(self.summary_lines),
        }


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Load a JSON file without schema normalization."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, list):
        raise ValueError("Phase1 列表格式已弃用，请使用 Canonical Schema (dict) 输入")
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是 dict (Canonical Schema)")

    return data


def _resolve_rule_thresholds(
    custom_thresholds: Optional[Dict[RegressionRuleId, float]] = None,
) -> Dict[RegressionRuleId, float]:
    thresholds = {rule_id: rule.threshold for rule_id, rule in DEFAULT_RULES.items()}
    if custom_thresholds:
        thresholds.update(custom_thresholds)
    return thresholds


def run_comparison(
    baseline_data: Dict[str, Any],
    target_data: Dict[str, Any],
    baseline_name: str,
    target_name: str,
    custom_thresholds: Optional[Dict[RegressionRuleId, float]] = None,
    align_strategy: str = "signature",
) -> tuple[DiffResult, RegressionReport]:
    """Run diff engine + regression detector."""
    engine = DiffEngine(align_strategy=align_strategy)
    diff_result = engine.compare(baseline_data, target_data)
    diff_result.baseline_file = baseline_name
    diff_result.target_file = target_name

    detector = RegressionDetector(custom_thresholds=custom_thresholds)
    regression_report = detector.detect(diff_result)

    return diff_result, regression_report


def _threshold_percent(decimal_value: float) -> float:
    return round(decimal_value * 100.0, 1)


def _source_kind(payload: Dict[str, Any]) -> str:
    source_schema = str(payload.get("_source_schema", "") or "").strip()
    if source_schema == "snapshot.v1":
        return "snapshot.v1"
    if source_schema == "1.0":
        return "canonical.v1"
    if payload.get("schema_version") == "snapshot.v1":
        return "snapshot.v1"
    if payload.get("schema_version") == "1.0":
        return "canonical.v1"
    return "capturedata"


def _compat_mode(baseline_data: Dict[str, Any], target_data: Dict[str, Any]) -> str:
    baseline_kind = _source_kind(baseline_data)
    target_kind = _source_kind(target_data)
    if "snapshot.v1" in (baseline_kind, target_kind):
        return "snapshot_aliases"
    if "canonical.v1" in (baseline_kind, target_kind):
        return "canonical_v1"
    return "legacy_capturedata"


def _metric_payload(metric: MetricDiff) -> Dict[str, Any]:
    return {
        "baseline": metric.baseline,
        "target": metric.target,
        "delta": metric.delta,
        "delta_percent": metric.delta_percent,
    }


def _resource_changes(diff_result: DiffResult) -> Dict[str, Any]:
    return {
        "textures": {
            "added": diff_result.textures_added,
            "removed": diff_result.textures_removed,
            "modified": diff_result.textures_modified,
        },
        "shaders": {
            "added": diff_result.shaders_added,
            "removed": diff_result.shaders_removed,
            "modified": diff_result.shaders_modified,
        },
        "buffers": {
            "added": len([b for b in diff_result.buffer_diffs if b.status.value == "added"]),
            "removed": len([b for b in diff_result.buffer_diffs if b.status.value == "removed"]),
            "modified": len([b for b in diff_result.buffer_diffs if b.status.value == "modified"]),
        },
        "draw_calls": {
            "added": diff_result.draw_calls_added,
            "removed": diff_result.draw_calls_removed,
            "modified": len([d for d in diff_result.draw_call_diffs if d.status.value == "modified"]),
        },
    }


def _issue_to_json(issue: RegressionIssue) -> Dict[str, Any]:
    return {
        "rule_id": issue.rule_id.value if hasattr(issue.rule_id, "value") else str(issue.rule_id),
        "severity": issue.severity.value,
        "message": issue.message,
        "details": issue.details,
        "baseline_value": issue.baseline_value,
        "target_value": issue.target_value,
        "delta_percent": issue.delta_percent,
        "affected_resources": list(issue.affected_resources),
        "evidence": [
            {
                "event_id": anchor.event_id,
                "marker_path": anchor.marker_path,
                "description": anchor.description,
            }
            for anchor in issue.evidence
        ],
    }


def _metric_for_rule(diff_result: DiffResult, rule_id: RegressionRuleId) -> Optional[MetricDiff]:
    if rule_id == RegressionRuleId.REG001:
        return diff_result.summary.draw_calls
    if rule_id == RegressionRuleId.REG003:
        return diff_result.summary.shader_changes
    if rule_id == RegressionRuleId.REG004:
        return diff_result.summary.buffer_memory
    if rule_id == RegressionRuleId.REG005:
        return diff_result.summary.triangles
    return None


def _normalize_gate_severity(severity: RegressionSeverity) -> RegressionSeverity:
    if severity == RegressionSeverity.WARNING:
        return RegressionSeverity.MEDIUM
    return severity


def _result_from_issue(
    issue: RegressionIssue,
    diff_result: DiffResult,
    rule_thresholds: Dict[RegressionRuleId, float],
) -> RegressionResult:
    metric = _metric_for_rule(diff_result, issue.rule_id)
    baseline_value = issue.baseline_value
    target_value = issue.target_value
    delta_percent = issue.delta_percent

    if metric is not None:
        if baseline_value is None:
            baseline_value = metric.baseline
        if target_value is None:
            target_value = metric.target
        if delta_percent is None:
            delta_percent = metric.delta_percent

    return RegressionResult(
        rule_id=issue.rule_id,
        severity=_normalize_gate_severity(issue.severity),
        category=RULE_CATEGORY.get(issue.rule_id, "General"),
        metric_name=RULE_METRIC_NAME.get(issue.rule_id, issue.rule_id.value.lower()),
        baseline_value=float(baseline_value or 0),
        target_value=float(target_value or 0),
        delta_percent=float(delta_percent or 0),
        threshold_percent=float(rule_thresholds.get(issue.rule_id, 0.0)),
        message=issue.message,
        details=issue.details,
    )


def _synthetic_metric_result(
    *,
    rule_id: RegressionRuleId,
    severity: RegressionSeverity,
    category: str,
    metric_name: str,
    metric: MetricDiff,
    threshold_percent: float,
    message: str,
    details: str,
) -> RegressionResult:
    return RegressionResult(
        rule_id=rule_id,
        severity=_normalize_gate_severity(severity),
        category=category,
        metric_name=metric_name,
        baseline_value=float(metric.baseline),
        target_value=float(metric.target),
        delta_percent=float(metric.delta_percent),
        threshold_percent=float(threshold_percent),
        message=message,
        details=details,
    )


def _dedupe_results(results: List[RegressionResult]) -> List[RegressionResult]:
    deduped: List[RegressionResult] = []
    seen = set()
    for result in results:
        key = (
            result.rule_id.value,
            result.metric_name,
            round(result.baseline_value, 6),
            round(result.target_value, 6),
            round(result.delta_percent, 6),
            result.message,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _check_name(result: RegressionResult) -> str:
    metric_name = result.metric_name
    aliases = {
        "draw_call_count": "draw_calls",
        "triangle_count": "triangles",
        "texture_count": "textures",
        "buffer_count": "buffers",
        "new_passes": "new_passes",
    }
    return aliases.get(metric_name, metric_name)


def _is_gate_failure(result: RegressionResult) -> bool:
    return result.severity in WARNING_SEVERITIES or result.severity == RegressionSeverity.CRITICAL


def _format_value(metric_name: str, value: float) -> str:
    numeric_value = float(value)
    if "memory" in metric_name:
        return f"{numeric_value / 1024 / 1024:.2f} MB"
    if numeric_value.is_integer():
        return f"{int(numeric_value):,}"
    return f"{numeric_value:.2f}"


def _build_ci_summary_lines(
    status: str,
    exit_code: int,
    failing_checks: List[str],
    failing_results: List[RegressionResult],
) -> List[str]:
    if not failing_results:
        return [f"status={status} exit_code={exit_code}", "No CI regressions detected."]

    lines = [
        f"status={status} exit_code={exit_code}",
        f"failing_checks={','.join(failing_checks)}",
    ]
    for result in failing_results:
        lines.append(
            (
                f"{_check_name(result)}: "
                f"{_format_value(result.metric_name, result.baseline_value)} -> "
                f"{_format_value(result.metric_name, result.target_value)} "
                f"({result.delta_percent:+.1f}% > {result.threshold_percent:.1f}%) "
                f"[{result.severity.value}]"
            )
        )
    return lines


def build_ci_verdict(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    baseline_data: Dict[str, Any],
    target_data: Dict[str, Any],
    rule_thresholds: Dict[RegressionRuleId, float],
    texture_mem_threshold: float,
    buffer_mem_threshold: float,
) -> CIVerdict:
    """Attach RegressionResult entries and synthesize CI verdict."""
    results = [_result_from_issue(issue, diff_result, rule_thresholds) for issue in regression_report.issues]

    texture_metric = diff_result.summary.texture_memory
    texture_threshold_percent = _threshold_percent(texture_mem_threshold)
    if texture_metric.delta > 0 and texture_metric.delta_percent > texture_threshold_percent:
        results.append(
            _synthetic_metric_result(
                rule_id=RegressionRuleId.REG002,
                severity=RegressionSeverity.WARNING,
                category="TextureMemory",
                metric_name="texture_memory",
                metric=texture_metric,
                threshold_percent=texture_threshold_percent,
                message=f"纹理内存增加了 {texture_metric.delta_percent:.1f}%",
                details=(
                    f"总纹理内存从 {_format_value('texture_memory', texture_metric.baseline)} "
                    f"增加到 {_format_value('texture_memory', texture_metric.target)}"
                ),
            )
        )

    buffer_metric = diff_result.summary.buffer_memory
    buffer_threshold_percent = _threshold_percent(buffer_mem_threshold)
    has_buffer_result = any(result.metric_name == "buffer_memory" for result in results)
    if (
        not has_buffer_result
        and buffer_metric.delta > 0
        and buffer_metric.delta_percent > buffer_threshold_percent
    ):
        results.append(
            _synthetic_metric_result(
                rule_id=RegressionRuleId.REG004,
                severity=RegressionSeverity.WARNING,
                category="BufferMemory",
                metric_name="buffer_memory",
                metric=buffer_metric,
                threshold_percent=buffer_threshold_percent,
                message=f"Buffer 内存增加了 {buffer_metric.delta_percent:.1f}%",
                details=(
                    f"总 Buffer 内存从 {_format_value('buffer_memory', buffer_metric.baseline)} "
                    f"增加到 {_format_value('buffer_memory', buffer_metric.target)}"
                ),
            )
        )

    results = _dedupe_results(results)
    regression_report.results = results

    exporter = JUnitXMLExporter()
    exit_code = exporter.get_exit_code(regression_report)
    if exit_code == exporter.EXIT_CRITICAL:
        status = "critical"
    elif exit_code == exporter.EXIT_WARNING:
        status = "warning"
    else:
        status = "pass"

    failing_results = [result for result in results if _is_gate_failure(result)]
    failing_checks: List[str] = []
    for result in failing_results:
        check_name = _check_name(result)
        if check_name not in failing_checks:
            failing_checks.append(check_name)

    thresholds = {
        "draw_call_percent": _threshold_percent(rule_thresholds[RegressionRuleId.REG001] / 100.0),
        "triangle_percent": _threshold_percent(rule_thresholds[RegressionRuleId.REG005] / 100.0),
        "texture_memory_percent": texture_threshold_percent,
        "buffer_memory_percent": buffer_threshold_percent,
    }

    return CIVerdict(
        status=status,
        exit_code=exit_code,
        thresholds=thresholds,
        failing_checks=failing_checks,
        summary_lines=_build_ci_summary_lines(status, exit_code, failing_checks, failing_results),
        results=results,
    )


def _count_summary_block(baseline_value: int, target_value: int) -> Dict[str, Any]:
    metric = MetricDiff("snapshot_count", baseline_value, target_value)
    return {
        "baseline": baseline_value,
        "target": target_value,
        "delta": metric.delta,
        "delta_percent": metric.delta_percent,
    }


def build_snapshot_summary(
    baseline_data: Dict[str, Any],
    target_data: Dict[str, Any],
) -> Dict[str, Any]:
    baseline_counts = baseline_data.get("_snapshot_counts", {}) or {}
    target_counts = target_data.get("_snapshot_counts", {}) or {}

    counts = {
        key: _count_summary_block(
            int(baseline_counts.get(key, 0) or 0),
            int(target_counts.get(key, 0) or 0),
        )
        for key in SNAPSHOT_COUNT_KEYS
    }

    baseline_availability = baseline_data.get("_snapshot_availability", {}) or {}
    target_availability = target_data.get("_snapshot_availability", {}) or {}
    baseline_missing = sorted(set(baseline_availability.get("missing_fields", []) or []))
    target_missing = sorted(set(target_availability.get("missing_fields", []) or []))

    return {
        "counts": counts,
        "availability": {
            "baseline_status": baseline_availability.get("status", "n/a"),
            "target_status": target_availability.get("status", "n/a"),
            "new_missing_fields": sorted(set(target_missing) - set(baseline_missing)),
            "resolved_missing_fields": sorted(set(baseline_missing) - set(target_missing)),
        },
    }


def build_json_diff(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    baseline_data: Dict[str, Any],
    target_data: Dict[str, Any],
    ci_verdict: CIVerdict,
) -> Dict[str, Any]:
    snapshot_summary = build_snapshot_summary(baseline_data, target_data)
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "baseline_file": diff_result.baseline_file,
            "target_file": diff_result.target_file,
            "tool_version": TOOL_VERSION,
        },
        "input": {
            "baseline_kind": _source_kind(baseline_data),
            "target_kind": _source_kind(target_data),
            "compat_mode": _compat_mode(baseline_data, target_data),
        },
        "summary": {
            "draw_calls": _metric_payload(diff_result.summary.draw_calls),
            "triangles": _metric_payload(diff_result.summary.triangles),
            "vertices": _metric_payload(diff_result.summary.vertices),
            "texture_memory_bytes": _metric_payload(diff_result.summary.texture_memory),
            "buffer_memory_bytes": _metric_payload(diff_result.summary.buffer_memory),
        },
        "snapshot_summary": snapshot_summary,
        "regressions": {
            "has_critical": regression_report.has_critical,
            "has_warning": regression_report.has_warning,
            "issues": [_issue_to_json(issue) for issue in regression_report.issues],
            "results": [result.to_dict() for result in regression_report.results],
        },
        "ci": ci_verdict.to_dict(),
        "resource_changes": _resource_changes(diff_result),
    }


def export_html_report(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    output_path: str,
    config: Optional[DiffHTMLConfig] = None,
) -> str:
    exporter = DiffHTMLExporter(config or DiffHTMLConfig())
    html_content = exporter.export(diff_result, regression_report)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as handle:
        handle.write(html_content)

    return str(output)


def export_json_diff(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    output_path: str,
    baseline_data: Dict[str, Any],
    target_data: Dict[str, Any],
    ci_verdict: CIVerdict,
) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = build_json_diff(diff_result, regression_report, baseline_data, target_data, ci_verdict)

    with open(output, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

    return str(output)


def export_junit_report(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    output_path: str,
) -> str:
    exporter = JUnitXMLExporter()
    return exporter.save(output_path, diff_result, regression_report)


def print_summary(
    diff_result: DiffResult,
    regression_report: RegressionReport,
    ci_verdict: Optional[CIVerdict] = None,
) -> None:
    print()
    print("=" * 60)
    print("RDC 对比分析结果")
    print("=" * 60)
    print()

    print(f"  基准文件: {diff_result.baseline_file}")
    print(f"  目标文件: {diff_result.target_file}")
    print()

    print("指标变化:")
    print("-" * 40)
    metrics = [
        ("Draw Calls", diff_result.summary.draw_calls, "draw_calls"),
        ("三角形", diff_result.summary.triangles, "triangles"),
        ("顶点", diff_result.summary.vertices, "vertices"),
        ("纹理内存", diff_result.summary.texture_memory, "texture_memory"),
        ("Buffer 内存", diff_result.summary.buffer_memory, "buffer_memory"),
    ]

    for label, metric, metric_name in metrics:
        if "memory" in metric_name:
            baseline_text = _format_value(metric_name, float(metric.baseline))
            target_text = _format_value(metric_name, float(metric.target))
            delta_text = f"{metric.delta / 1024 / 1024:+.2f} MB"
        else:
            baseline_text = f"{int(metric.baseline):,}"
            target_text = f"{int(metric.target):,}"
            delta_text = f"{int(metric.delta):+,}"
        percent_text = f"({metric.delta_percent:+.1f}%)" if metric.delta != 0 else ""
        print(f"  {label:12s}: {baseline_text} -> {target_text}  [{delta_text} {percent_text}]")

    print()
    print("资源变化:")
    print("-" * 40)
    for name, stats in _resource_changes(diff_result).items():
        total_changes = stats["added"] + stats["removed"] + stats["modified"]
        if total_changes > 0:
            print(
                f"  {name:12s}: +{stats['added']} 新增, -{stats['removed']} 移除, ~{stats['modified']} 修改"
            )
        else:
            print(f"  {name:12s}: 无变化")

    print()
    print("回归检测:")
    print("-" * 40)
    if not regression_report.issues:
        print("  [OK] 未检测到规则级回归问题")
    else:
        critical = [issue for issue in regression_report.issues if issue.severity == RegressionSeverity.CRITICAL]
        warnings = [issue for issue in regression_report.issues if issue.severity in WARNING_SEVERITIES]
        infos = [
            issue
            for issue in regression_report.issues
            if issue.severity not in WARNING_SEVERITIES and issue.severity != RegressionSeverity.CRITICAL
        ]

        if critical:
            print(f"  严重问题 ({len(critical)}):")
            for issue in critical:
                print(f"    - [{issue.rule_id.value}] {issue.message}")
        if warnings:
            print(f"  警告 ({len(warnings)}):")
            for issue in warnings[:5]:
                print(f"    - [{issue.rule_id.value}] {issue.message}")
            if len(warnings) > 5:
                print(f"    ... 还有 {len(warnings) - 5} 个警告")
        if infos:
            print(f"  提示 ({len(infos)}):")
            for issue in infos[:3]:
                print(f"    - [{issue.rule_id.value}] {issue.message}")
            if len(infos) > 3:
                print(f"    ... 还有 {len(infos) - 3} 个提示")

    if ci_verdict is not None:
        print()
        print("CI 门禁:")
        print("-" * 40)
        for line in ci_verdict.summary_lines:
            print(f"  {line}")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RDC 对比分析工具 - 检测两个捕获之间的差异和回归",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s baseline.json target.json --html report.html
  %(prog)s baseline.json target.json --json diff.json --junit junit.xml
  %(prog)s baseline.json target.json --triangle-threshold 0.2 --draw-call-threshold 0.1

退出码:
  0  无门禁回归
  1  警告级门禁回归
  2  严重级门禁回归
  3  compare 执行异常
        """,
    )

    parser.add_argument("baseline", help="基准文件 (.json/.xml/.rdc)")
    parser.add_argument("target", help="目标文件 (.json/.xml/.rdc)")
    parser.add_argument("--html", "-o", dest="html_output", help="输出 HTML 报告路径")
    parser.add_argument("--json", "-j", dest="json_output", help="输出 JSON 差异文件路径")
    parser.add_argument("--junit", dest="junit_output", help="输出 JUnit XML 路径")
    parser.add_argument(
        "--triangle-threshold",
        type=float,
        default=0.2,
        help="三角形增加阈值 (默认: 0.2 = 20%%)",
    )
    parser.add_argument(
        "--draw-call-threshold",
        type=float,
        default=0.1,
        help="Draw Call 增加阈值 (默认: 0.1 = 10%%)",
    )
    parser.add_argument(
        "--texture-mem-threshold",
        type=float,
        default=0.3,
        help="纹理内存增加阈值 (默认: 0.3 = 30%%)",
    )
    parser.add_argument(
        "--buffer-mem-threshold",
        type=float,
        default=0.3,
        help="Buffer 内存增加阈值 (默认: 0.3 = 30%%)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式，不打印控制台摘要")
    parser.add_argument("--theme", choices=["dark", "light"], default="dark", help="HTML 报告主题")
    parser.add_argument("--version", action="version", version=f"RDC Compare Tool {TOOL_VERSION}")

    args = parser.parse_args()

    if not args.html_output and not args.json_output and not args.junit_output and args.quiet:
        print("[!] 错误: 静默模式下至少需要指定一个输出 (--html / --json / --junit)")
        return JUnitXMLExporter.EXIT_ERROR

    try:
        if not args.quiet:
            print(f"[*] 加载基准文件: {args.baseline}")
        baseline_data = load_capture_file(args.baseline, verbose=not args.quiet)

        if not args.quiet:
            print(f"[*] 加载目标文件: {args.target}")
        target_data = load_capture_file(args.target, verbose=not args.quiet)

        custom_thresholds = {
            RegressionRuleId.REG001: args.draw_call_threshold * 100.0,
            RegressionRuleId.REG004: args.buffer_mem_threshold * 100.0,
            RegressionRuleId.REG005: args.triangle_threshold * 100.0,
        }
        rule_thresholds = _resolve_rule_thresholds(custom_thresholds)

        if not args.quiet:
            print("[*] 执行对比分析...")
        diff_result, regression_report = run_comparison(
            baseline_data=baseline_data,
            target_data=target_data,
            baseline_name=Path(args.baseline).name,
            target_name=Path(args.target).name,
            custom_thresholds=custom_thresholds,
        )

        ci_verdict = build_ci_verdict(
            diff_result=diff_result,
            regression_report=regression_report,
            baseline_data=baseline_data,
            target_data=target_data,
            rule_thresholds=rule_thresholds,
            texture_mem_threshold=args.texture_mem_threshold,
            buffer_mem_threshold=args.buffer_mem_threshold,
        )

        if args.html_output:
            html_config = DiffHTMLConfig(theme=args.theme)
            html_path = export_html_report(diff_result, regression_report, args.html_output, html_config)
            if not args.quiet:
                print(f"[+] HTML 报告: {html_path}")

        if args.json_output:
            json_path = export_json_diff(
                diff_result,
                regression_report,
                args.json_output,
                baseline_data,
                target_data,
                ci_verdict,
            )
            if not args.quiet:
                print(f"[+] JSON 差异: {json_path}")

        if args.junit_output:
            junit_path = export_junit_report(diff_result, regression_report, args.junit_output)
            if not args.quiet:
                print(f"[+] JUnit XML: {junit_path}")

        if not args.quiet:
            print_summary(diff_result, regression_report, ci_verdict)

        return ci_verdict.exit_code

    except FileNotFoundError as exc:
        print(f"[!] 错误: {exc}")
        return JUnitXMLExporter.EXIT_ERROR
    except json.JSONDecodeError as exc:
        print(f"[!] JSON 解析错误: {exc}")
        return JUnitXMLExporter.EXIT_ERROR
    except ValueError as exc:
        print(f"[!] 输入错误: {exc}")
        return JUnitXMLExporter.EXIT_ERROR
    except Exception as exc:  # pragma: no cover - fallback error path
        print(f"[!] 分析失败: {exc}")
        return JUnitXMLExporter.EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
