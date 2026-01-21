#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试多帧统计采样模块
==================

测试 stats/ 目录下的 sampler.py 和 summary.py 模块。
"""

import pytest
import math
from typing import Dict, Any

# 测试模块
from rdc_analyzer.stats.sampler import (
    MetricStatistics,
    FrameSample,
    AggregatedMetrics,
    MultiFrameSampler,
)
from rdc_analyzer.stats.summary import (
    SignificanceLevel,
    MetricComparison,
    ComparisonResult,
    StatisticalSummary,
)


# ============================================================================
# MetricStatistics Tests
# ============================================================================

class TestMetricStatistics:
    """测试 MetricStatistics 类"""
    
    def test_empty_values(self):
        """测试空值列表"""
        stats = MetricStatistics()
        assert stats.count == 0
        assert stats.mean == 0.0
        assert stats.median == 0.0
        assert stats.std == 0.0
        assert stats.cv == 0.0
    
    def test_single_value(self):
        """测试单个值"""
        stats = MetricStatistics(values=[100.0])
        assert stats.count == 1
        assert stats.mean == 100.0
        assert stats.median == 100.0
        assert stats.std == 0.0  # 单个值无标准差
    
    def test_multiple_values(self):
        """测试多个值"""
        stats = MetricStatistics(values=[10.0, 20.0, 30.0, 40.0, 50.0])
        assert stats.count == 5
        assert stats.mean == 30.0
        assert stats.median == 30.0
        assert stats.min == 10.0
        assert stats.max == 50.0
    
    def test_cv_calculation(self):
        """测试变异系数计算"""
        # CV = std / mean
        stats = MetricStatistics(values=[100.0, 100.0, 100.0])  # 无波动
        assert stats.cv == 0.0
        
        # 有波动的数据
        stats2 = MetricStatistics(values=[80.0, 100.0, 120.0])
        assert stats2.cv > 0
        assert stats2.cv < 0.3  # 应该是中等波动
    
    def test_percentiles(self):
        """测试百分位数"""
        values = list(range(1, 101))  # 1 到 100
        stats = MetricStatistics(values=values)
        # P95 应该接近 95-96 (取决于计算方法)
        assert 95 <= stats.p95 <= 96
        assert 99 <= stats.p99 <= 100
    
    def test_to_dict(self):
        """测试转换为字典"""
        stats = MetricStatistics(values=[10.0, 20.0, 30.0])
        d = stats.to_dict()
        assert "count" in d
        assert "mean" in d
        assert "std" in d
        assert "cv" in d
        assert d["count"] == 3


# ============================================================================
# FrameSample Tests
# ============================================================================

class TestFrameSample:
    """测试 FrameSample 类"""
    
    def test_from_json_data_phase1_format(self):
        """测试从 Phase 1 格式 JSON 创建"""
        data = {
            "statistics": {
                "totalDrawCalls": 100,
                "totalVertices": 50000,
                "totalTriangles": 16666,
                "textureCount": 20,
                "shaderCount": 15,
            },
            "textures": [{"size_bytes": 1024}, {"size_bytes": 2048}],
            "buffers": [{"size_bytes": 4096}],
        }
        sample = FrameSample.from_json_data(data, "test.json", 0)
        
        assert sample.draw_calls == 100
        assert sample.vertices == 50000
        assert sample.triangles == 16666
        assert sample.texture_count == 20
        assert sample.texture_memory_bytes == 3072
        assert sample.buffer_count == 1
        assert sample.buffer_memory_bytes == 4096
        assert sample.source_file == "test.json"
    
    def test_from_json_data_phase2_format(self):
        """测试从 Phase 2 格式 JSON 创建"""
        data = {
            "summary": {
                "draw_call_count": 200,
                "total_vertices": 100000,
                "total_triangles": 33333,
                "texture_count": 30,
                "shader_count": 25,
            },
            "textures": [],
            "buffers": [],
        }
        sample = FrameSample.from_json_data(data, "test2.json", 1)
        
        assert sample.draw_calls == 200
        assert sample.vertices == 100000
        assert sample.triangles == 33333


# ============================================================================
# MultiFrameSampler Tests
# ============================================================================

class TestMultiFrameSampler:
    """测试 MultiFrameSampler 类"""
    
    def test_empty_sampler(self):
        """测试空采样器"""
        sampler = MultiFrameSampler()
        assert sampler.sample_count == 0
        
        aggregated = sampler.aggregate()
        assert aggregated.sample_count == 0
    
    def test_add_samples(self):
        """测试添加样本"""
        sampler = MultiFrameSampler()
        
        # 添加 3 个样本
        for i in range(3):
            sample = FrameSample(
                draw_calls=100 + i * 10,
                vertices=50000 + i * 1000,
                triangles=16666 + i * 333,
            )
            sampler.add_sample(sample)
        
        assert sampler.sample_count == 3
    
    def test_aggregate_statistics(self):
        """测试聚合统计"""
        sampler = MultiFrameSampler()
        
        # 添加固定值样本
        for _ in range(5):
            sample = FrameSample(draw_calls=100, vertices=50000, triangles=16666)
            sampler.add_sample(sample)
        
        aggregated = sampler.aggregate()
        
        assert aggregated.sample_count == 5
        assert aggregated.draw_calls.mean == 100.0
        assert aggregated.draw_calls.std == 0.0  # 无波动
        assert aggregated.vertices.mean == 50000.0
    
    def test_add_sample_from_json(self):
        """测试从 JSON 添加样本"""
        sampler = MultiFrameSampler()
        
        data = {
            "statistics": {
                "totalDrawCalls": 150,
                "totalVertices": 75000,
            }
        }
        sampler.add_sample_from_json(data, "frame1.json")
        
        assert sampler.sample_count == 1
        aggregated = sampler.aggregate()
        assert aggregated.draw_calls.mean == 150.0
    
    def test_stability_report(self):
        """测试稳定性报告"""
        sampler = MultiFrameSampler()
        
        # 添加稳定数据
        for _ in range(5):
            sample = FrameSample(draw_calls=100, vertices=50000)
            sampler.add_sample(sample)
        
        report = sampler.get_stability_report()
        
        assert report["sample_count"] == 5
        assert "metrics" in report
        assert report["metrics"]["draw_calls"]["stability"] == "excellent"
        assert report["overall_stability"] == "excellent"
    
    def test_stability_report_unstable_data(self):
        """测试不稳定数据的稳定性报告"""
        sampler = MultiFrameSampler()
        
        # 添加高波动数据
        values = [100, 500, 50, 800, 30]  # 高变异
        for v in values:
            sample = FrameSample(draw_calls=v, vertices=50000)
            sampler.add_sample(sample)
        
        report = sampler.get_stability_report()
        # draw_calls 的 CV 应该很高
        assert report["metrics"]["draw_calls"]["cv"] > 0.3


# ============================================================================
# AggregatedMetrics Tests
# ============================================================================

class TestAggregatedMetrics:
    """测试 AggregatedMetrics 类"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        metrics = AggregatedMetrics(sample_count=5)
        metrics.draw_calls.values = [100.0, 110.0, 105.0]
        
        d = metrics.to_dict()
        
        assert d["sample_count"] == 5
        assert "metrics" in d
        assert "draw_calls" in d["metrics"]
    
    def test_to_compare_data(self):
        """测试转换为 DiffEngine 兼容格式"""
        metrics = AggregatedMetrics(sample_count=3)
        metrics.draw_calls.values = [100.0, 100.0, 100.0]
        metrics.vertices.values = [50000.0, 50000.0, 50000.0]
        
        compare_data = metrics.to_compare_data()
        
        assert "statistics" in compare_data
        assert compare_data["statistics"]["totalDrawCalls"] == 100
        assert compare_data["statistics"]["totalVertices"] == 50000


# ============================================================================
# StatisticalSummary Tests
# ============================================================================

class TestStatisticalSummary:
    """测试 StatisticalSummary 类"""
    
    def test_compare_identical_data(self):
        """测试相同数据的对比"""
        summary = StatisticalSummary(confidence_level=0.95)
        
        baseline = AggregatedMetrics(sample_count=5)
        baseline.draw_calls.values = [100.0] * 5
        baseline.vertices.values = [50000.0] * 5
        
        target = AggregatedMetrics(sample_count=5)
        target.draw_calls.values = [100.0] * 5
        target.vertices.values = [50000.0] * 5
        
        result = summary.compare(baseline, target)
        
        assert not result.has_significant_regression
        assert len(result.significant_metrics) == 0
    
    def test_compare_significant_regression(self):
        """测试显著回归检测"""
        summary = StatisticalSummary(confidence_level=0.95)
        
        # 基准: 100 draw calls，低波动
        baseline = AggregatedMetrics(sample_count=10)
        baseline.draw_calls.values = [100.0] * 10
        
        # 目标: 200 draw calls，明显增加
        target = AggregatedMetrics(sample_count=10)
        target.draw_calls.values = [200.0] * 10
        
        result = summary.compare(baseline, target)
        
        assert result.has_significant_regression
        assert "draw_calls" in result.significant_metrics
        
        # 检查 draw_calls 的对比结果
        dc_comp = result.metrics["draw_calls"]
        assert dc_comp.delta == 100.0
        assert dc_comp.delta_percent == 100.0  # 翻倍
        assert dc_comp.significance != SignificanceLevel.NOT_SIGNIFICANT
    
    def test_compare_no_regression_with_jitter(self):
        """测试有抖动但无显著回归"""
        summary = StatisticalSummary(confidence_level=0.95)
        
        # 基准: 100 ± 20
        baseline = AggregatedMetrics(sample_count=10)
        baseline.draw_calls.values = [80, 85, 90, 95, 100, 105, 110, 115, 120, 100]
        
        # 目标: 102 ± 20 (仅微小增加)
        target = AggregatedMetrics(sample_count=10)
        target.draw_calls.values = [82, 87, 92, 97, 102, 107, 112, 117, 122, 102]
        
        result = summary.compare(baseline, target)
        
        # 由于抖动较大，微小差异不应被视为显著
        dc_comp = result.metrics["draw_calls"]
        # Z 分数应该较小
        assert abs(dc_comp.z_score) < 2.0
    
    def test_significance_levels(self):
        """测试显著性级别分类"""
        summary = StatisticalSummary()
        
        # 测试内部分类方法
        assert summary._classify_significance(0.5) == SignificanceLevel.NOT_SIGNIFICANT
        assert summary._classify_significance(1.7) == SignificanceLevel.LOW
        assert summary._classify_significance(2.2) == SignificanceLevel.MEDIUM
        assert summary._classify_significance(3.0) == SignificanceLevel.HIGH
    
    def test_effect_size_calculation(self):
        """测试效应量计算"""
        summary = StatisticalSummary()
        
        # Cohen's d = (mean2 - mean1) / pooled_std
        d = summary._compute_effect_size(100, 10, 120, 10)
        assert d == 2.0  # (120-100) / sqrt((10^2+10^2)/2) = 20/10 = 2.0
    
    def test_confidence_interval(self):
        """测试置信区间计算"""
        summary = StatisticalSummary(confidence_level=0.95)
        
        # 两组相同数据
        ci_lower, ci_upper = summary._compute_confidence_interval(
            100, 0, 10,  # mean=100, std=0, n=10
            100, 0, 10   # mean=100, std=0, n=10
        )
        assert ci_lower == 0.0
        assert ci_upper == 0.0


# ============================================================================
# ComparisonResult Tests
# ============================================================================

class TestComparisonResult:
    """测试 ComparisonResult 类"""
    
    def test_is_significant(self):
        """测试显著性判断"""
        result = ComparisonResult()
        result.metrics["draw_calls"] = MetricComparison(
            metric_name="draw_calls",
            delta=50.0,
            significance=SignificanceLevel.HIGH,
        )
        result.metrics["vertices"] = MetricComparison(
            metric_name="vertices",
            delta=-10.0,  # 减少，不是回归
            significance=SignificanceLevel.HIGH,
        )
        
        assert result.is_significant("draw_calls")  # 增加且显著
        assert not result.is_significant("vertices")  # 减少，虽然显著但不是回归
        assert not result.is_significant("unknown")  # 不存在的指标
    
    def test_get_regression_summary(self):
        """测试回归摘要生成"""
        result = ComparisonResult(has_significant_regression=True)
        result.significant_metrics = ["draw_calls"]
        result.metrics["draw_calls"] = MetricComparison(
            metric_name="draw_calls",
            delta=100.0,
            delta_percent=50.0,
            significance=SignificanceLevel.HIGH,
        )
        
        summary = result.get_regression_summary()
        assert "draw_calls" in summary
        assert "50.0%" in summary
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = ComparisonResult(
            baseline_samples=5,
            target_samples=5,
            has_significant_regression=False,
        )
        
        d = result.to_dict()
        
        assert d["baseline_samples"] == 5
        assert d["target_samples"] == 5
        assert d["has_significant_regression"] is False


# ============================================================================
# Integration Tests
# ============================================================================

class TestStatisticsIntegration:
    """端到端集成测试"""
    
    def test_full_workflow(self):
        """测试完整的多帧对比工作流"""
        # 1. 创建采样器并添加基准样本
        baseline_sampler = MultiFrameSampler()
        for i in range(5):
            sample = FrameSample(
                draw_calls=100 + i,  # 100-104
                vertices=50000,
                triangles=16666,
            )
            baseline_sampler.add_sample(sample)
        
        # 2. 创建目标采样器 (有回归)
        target_sampler = MultiFrameSampler()
        for i in range(5):
            sample = FrameSample(
                draw_calls=150 + i,  # 150-154，增加 ~50%
                vertices=50000,
                triangles=16666,
            )
            target_sampler.add_sample(sample)
        
        # 3. 聚合
        baseline_agg = baseline_sampler.aggregate()
        target_agg = target_sampler.aggregate()
        
        # 4. 对比
        summary = StatisticalSummary(confidence_level=0.95)
        result = summary.compare(baseline_agg, target_agg)
        
        # 5. 验证结果
        assert result.baseline_samples == 5
        assert result.target_samples == 5
        assert result.has_significant_regression
        assert "draw_calls" in result.significant_metrics
        
        # 6. 格式化输出
        formatted = summary.format_summary(result)
        assert "draw_calls" in formatted
        assert "150" in formatted or "152" in formatted  # 目标均值
    
    def test_json_roundtrip(self):
        """测试 JSON 序列化往返"""
        import json
        
        # 创建结果
        result = ComparisonResult(
            baseline_samples=10,
            target_samples=10,
            has_significant_regression=True,
            significant_metrics=["draw_calls"],
            overall_confidence="high",
        )
        result.metrics["draw_calls"] = MetricComparison(
            metric_name="draw_calls",
            baseline_mean=100.0,
            baseline_std=5.0,
            baseline_count=10,
            target_mean=150.0,
            target_std=5.0,
            target_count=10,
            delta=50.0,
            delta_percent=50.0,
            significance=SignificanceLevel.HIGH,
            z_score=3.5,
            effect_size=2.0,
        )
        
        # 序列化
        d = result.to_dict()
        json_str = json.dumps(d, indent=2)
        
        # 反序列化
        parsed = json.loads(json_str)
        
        assert parsed["baseline_samples"] == 10
        assert parsed["has_significant_regression"] is True
        assert parsed["metrics"]["draw_calls"]["delta"] == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
