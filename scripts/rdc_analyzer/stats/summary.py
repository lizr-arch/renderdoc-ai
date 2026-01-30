#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计摘要与显著性检测
====================

提供多帧统计对比和显著性检测功能。

用法:
    summary = StatisticalSummary()
    result = summary.compare(baseline_aggregated, target_aggregated)
    
    if result.is_significant("draw_calls"):
        print("Draw Calls 回归具有统计显著性")
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import math

from .sampler import AggregatedMetrics, MetricStatistics


class SignificanceLevel(Enum):
    """显著性级别"""
    
    NOT_SIGNIFICANT = "not_significant"  # 无显著差异
    LOW = "low"                          # 低显著性 (p < 0.1)
    MEDIUM = "medium"                    # 中等显著性 (p < 0.05)
    HIGH = "high"                        # 高显著性 (p < 0.01)


@dataclass
class MetricComparison:
    """单个指标的对比结果"""
    
    metric_name: str
    
    # 基准统计
    baseline_mean: float = 0.0
    baseline_std: float = 0.0
    baseline_count: int = 0
    
    # 目标统计
    target_mean: float = 0.0
    target_std: float = 0.0
    target_count: int = 0
    
    # 差异
    delta: float = 0.0
    delta_percent: float = 0.0
    
    # 显著性
    significance: SignificanceLevel = SignificanceLevel.NOT_SIGNIFICANT
    z_score: float = 0.0
    effect_size: float = 0.0  # Cohen's d
    
    # 置信区间 (95%)
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "metric": self.metric_name,
            "baseline": {
                "mean": round(self.baseline_mean, 2),
                "std": round(self.baseline_std, 2),
                "count": self.baseline_count,
            },
            "target": {
                "mean": round(self.target_mean, 2),
                "std": round(self.target_std, 2),
                "count": self.target_count,
            },
            "delta": round(self.delta, 2),
            "delta_percent": round(self.delta_percent, 2),
            "significance": self.significance.value,
            "z_score": round(self.z_score, 3),
            "effect_size": round(self.effect_size, 3),
            "confidence_interval_95": {
                "lower": round(self.ci_lower, 2),
                "upper": round(self.ci_upper, 2),
            },
        }


@dataclass
class ComparisonResult:
    """多帧统计对比结果"""
    
    # 各指标对比
    metrics: Dict[str, MetricComparison] = field(default_factory=dict)
    
    # 采样信息
    baseline_samples: int = 0
    target_samples: int = 0
    
    # 总体判断
    has_significant_regression: bool = False
    significant_metrics: List[str] = field(default_factory=list)
    
    # 置信度
    overall_confidence: str = "low"  # low/medium/high
    
    def is_significant(self, metric_name: str) -> bool:
        """检查指标是否有显著回归
        
        Args:
            metric_name: 指标名称
            
        Returns:
            True 如果该指标有显著回归 (且是恶化方向)
        """
        if metric_name not in self.metrics:
            return False
        
        comp = self.metrics[metric_name]
        
        # 显著性级别至少为 LOW
        if comp.significance == SignificanceLevel.NOT_SIGNIFICANT:
            return False
        
        # delta > 0 表示增加 (对于 draw_calls/vertices/memory 等是恶化)
        return comp.delta > 0
    
    def get_regression_summary(self) -> str:
        """生成回归摘要
        
        Returns:
            人类可读的摘要文本
        """
        if not self.has_significant_regression:
            return "未检测到统计显著的性能回归"
        
        lines = ["检测到以下显著性能回归:"]
        for metric_name in self.significant_metrics:
            comp = self.metrics[metric_name]
            direction = "增加" if comp.delta > 0 else "减少"
            lines.append(
                f"  - {metric_name}: {direction} {abs(comp.delta_percent):.1f}% "
                f"(显著性: {comp.significance.value})"
            )
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "baseline_samples": self.baseline_samples,
            "target_samples": self.target_samples,
            "has_significant_regression": self.has_significant_regression,
            "significant_metrics": self.significant_metrics,
            "overall_confidence": self.overall_confidence,
            "metrics": {
                k: v.to_dict() for k, v in self.metrics.items()
            },
        }


class StatisticalSummary:
    """统计摘要生成器
    
    对比两组聚合数据，执行显著性检测。
    
    用法:
        summary = StatisticalSummary(confidence_level=0.95)
        result = summary.compare(baseline_aggregated, target_aggregated)
        
        print(result.get_regression_summary())
    """
    
    def __init__(self, confidence_level: float = 0.95):
        """初始化
        
        Args:
            confidence_level: 置信水平 (默认 0.95)
        """
        self.confidence_level = confidence_level
        
        # Z 值查表 (常用置信水平)
        self._z_table = {
            0.90: 1.645,
            0.95: 1.960,
            0.99: 2.576,
        }
    
    def _get_z_critical(self) -> float:
        """获取临界 Z 值"""
        return self._z_table.get(self.confidence_level, 1.960)
    
    def _compute_z_score(
        self,
        mean1: float,
        std1: float,
        n1: int,
        mean2: float,
        std2: float,
        n2: int
    ) -> float:
        """计算 Z 分数 (两样本均值比较)
        
        使用 Welch's t-test 近似 (样本量较小时更准确)
        
        Args:
            mean1, std1, n1: 第一组的均值、标准差、样本量
            mean2, std2, n2: 第二组的均值、标准差、样本量
            
        Returns:
            Z 分数
        """
        if n1 == 0 or n2 == 0:
            return 0.0
        
        # 处理标准差为 0 的情况
        if std1 == 0 and std2 == 0:
            # 两组数据完全相同
            if mean1 == mean2:
                return 0.0
            # 数据不同但无波动，返回极大值表示显著
            return float('inf') if mean2 > mean1 else float('-inf')
        
        # 计算标准误差
        se = math.sqrt((std1 ** 2 / n1) + (std2 ** 2 / n2))
        
        if se == 0:
            return 0.0
        
        return (mean2 - mean1) / se
    
    def _compute_effect_size(
        self,
        mean1: float,
        std1: float,
        mean2: float,
        std2: float
    ) -> float:
        """计算效应量 (Cohen's d)
        
        效应量解释:
        - |d| < 0.2: 小效应
        - 0.2 <= |d| < 0.5: 小到中等效应
        - 0.5 <= |d| < 0.8: 中等效应
        - |d| >= 0.8: 大效应
        
        Returns:
            Cohen's d 值
        """
        pooled_std = math.sqrt((std1 ** 2 + std2 ** 2) / 2)
        
        if pooled_std == 0:
            return 0.0
        
        return (mean2 - mean1) / pooled_std
    
    def _compute_confidence_interval(
        self,
        mean1: float,
        std1: float,
        n1: int,
        mean2: float,
        std2: float,
        n2: int
    ) -> Tuple[float, float]:
        """计算差值的置信区间
        
        Returns:
            (下界, 上界) 元组
        """
        if n1 == 0 or n2 == 0:
            return (0.0, 0.0)
        
        diff = mean2 - mean1
        se = math.sqrt((std1 ** 2 / n1) + (std2 ** 2 / n2))
        z = self._get_z_critical()
        
        margin = z * se
        return (diff - margin, diff + margin)
    
    def _classify_significance(self, z_score: float) -> SignificanceLevel:
        """根据 Z 分数判断显著性级别
        
        Args:
            z_score: Z 分数
            
        Returns:
            显著性级别
        """
        abs_z = abs(z_score)
        
        if abs_z >= 2.576:  # p < 0.01
            return SignificanceLevel.HIGH
        elif abs_z >= 1.960:  # p < 0.05
            return SignificanceLevel.MEDIUM
        elif abs_z >= 1.645:  # p < 0.1
            return SignificanceLevel.LOW
        else:
            return SignificanceLevel.NOT_SIGNIFICANT
    
    def _compare_metric(
        self,
        name: str,
        baseline: MetricStatistics,
        target: MetricStatistics
    ) -> MetricComparison:
        """对比单个指标
        
        Args:
            name: 指标名称
            baseline: 基准统计
            target: 目标统计
            
        Returns:
            MetricComparison 结果
        """
        # 计算差值
        delta = target.mean - baseline.mean
        delta_percent = 0.0
        if baseline.mean != 0:
            delta_percent = (delta / baseline.mean) * 100
        
        # 计算 Z 分数
        z_score = self._compute_z_score(
            baseline.mean, baseline.std, baseline.count,
            target.mean, target.std, target.count
        )
        
        # 计算效应量
        effect_size = self._compute_effect_size(
            baseline.mean, baseline.std,
            target.mean, target.std
        )
        
        # 计算置信区间
        ci_lower, ci_upper = self._compute_confidence_interval(
            baseline.mean, baseline.std, baseline.count,
            target.mean, target.std, target.count
        )
        
        # 判断显著性
        significance = self._classify_significance(z_score)
        
        return MetricComparison(
            metric_name=name,
            baseline_mean=baseline.mean,
            baseline_std=baseline.std,
            baseline_count=baseline.count,
            target_mean=target.mean,
            target_std=target.std,
            target_count=target.count,
            delta=delta,
            delta_percent=delta_percent,
            significance=significance,
            z_score=z_score,
            effect_size=effect_size,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        )
    
    def compare(
        self,
        baseline: AggregatedMetrics,
        target: AggregatedMetrics
    ) -> ComparisonResult:
        """对比两组聚合数据
        
        Args:
            baseline: 基准聚合数据
            target: 目标聚合数据
            
        Returns:
            ComparisonResult 对比结果
        """
        result = ComparisonResult(
            baseline_samples=baseline.sample_count,
            target_samples=target.sample_count,
        )
        
        # 对比各指标
        metric_pairs = [
            ("draw_calls", baseline.draw_calls, target.draw_calls),
            ("vertices", baseline.vertices, target.vertices),
            ("triangles", baseline.triangles, target.triangles),
            ("texture_count", baseline.texture_count, target.texture_count),
            ("texture_memory", baseline.texture_memory, target.texture_memory),
            ("buffer_count", baseline.buffer_count, target.buffer_count),
            ("buffer_memory", baseline.buffer_memory, target.buffer_memory),
            ("shader_count", baseline.shader_count, target.shader_count),
        ]
        
        for name, base_stat, target_stat in metric_pairs:
            comp = self._compare_metric(name, base_stat, target_stat)
            result.metrics[name] = comp
            
            # 检查是否有显著回归 (delta > 0 且显著)
            if comp.delta > 0 and comp.significance != SignificanceLevel.NOT_SIGNIFICANT:
                result.has_significant_regression = True
                result.significant_metrics.append(name)
        
        # 评估总体置信度
        min_samples = min(baseline.sample_count, target.sample_count)
        if min_samples >= 10:
            result.overall_confidence = "high"
        elif min_samples >= 5:
            result.overall_confidence = "medium"
        else:
            result.overall_confidence = "low"
        
        return result
    
    def format_summary(self, result: ComparisonResult) -> str:
        """格式化对比摘要
        
        Args:
            result: 对比结果
            
        Returns:
            格式化的摘要文本
        """
        lines = [
            "=" * 60,
            "多帧统计对比摘要",
            "=" * 60,
            "",
            f"基准样本数: {result.baseline_samples}",
            f"目标样本数: {result.target_samples}",
            f"置信水平: {self.confidence_level * 100:.0f}%",
            f"总体置信度: {result.overall_confidence}",
            "",
            "-" * 60,
            "指标对比:",
            "-" * 60,
        ]
        
        for name, comp in result.metrics.items():
            # 格式化数值
            if "memory" in name:
                # 内存用 MB
                base_str = f"{comp.baseline_mean / 1024 / 1024:.1f} MB"
                target_str = f"{comp.target_mean / 1024 / 1024:.1f} MB"
                delta_str = f"{comp.delta / 1024 / 1024:+.2f} MB"
            else:
                base_str = f"{comp.baseline_mean:,.0f}"
                target_str = f"{comp.target_mean:,.0f}"
                delta_str = f"{comp.delta:+,.0f}"
            
            # 显著性标记
            sig_mark = ""
            if comp.significance == SignificanceLevel.HIGH:
                sig_mark = " ***"
            elif comp.significance == SignificanceLevel.MEDIUM:
                sig_mark = " **"
            elif comp.significance == SignificanceLevel.LOW:
                sig_mark = " *"
            
            lines.append(
                f"  {name:20s}: {base_str} → {target_str}  "
                f"[{delta_str} ({comp.delta_percent:+.1f}%)]{sig_mark}"
            )
        
        lines.extend([
            "",
            "-" * 60,
            "显著性检测:",
            "-" * 60,
        ])
        
        if result.has_significant_regression:
            lines.append(f"  ⚠ 检测到 {len(result.significant_metrics)} 个显著回归指标:")
            for metric in result.significant_metrics:
                comp = result.metrics[metric]
                lines.append(
                    f"    - {metric}: {comp.significance.value} "
                    f"(Z={comp.z_score:.2f}, d={comp.effect_size:.2f})"
                )
        else:
            lines.append("  ✓ 未检测到统计显著的性能回归")
        
        lines.extend([
            "",
            "显著性说明: * p<0.1, ** p<0.05, *** p<0.01",
            "",
        ])
        
        return "\n".join(lines)
