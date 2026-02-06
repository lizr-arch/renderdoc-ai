#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计分析模块
============

提供多帧统计采样和显著性检测功能，支持 B-mode 回归门禁。

主要功能:
    - MultiFrameSampler: 多帧数据聚合采样
    - StatisticalSummary: 统计摘要 (mean/median/p95/std)
    - SignificanceTest: 显著性检测
"""

from .sampler import (
    MultiFrameSampler,
    FrameSample,
    AggregatedMetrics,
    MetricStatistics,
)

from .summary import (
    StatisticalSummary,
    ComparisonResult,
    SignificanceLevel,
)

__all__ = [
    # Sampler
    "MultiFrameSampler",
    "FrameSample",
    "AggregatedMetrics",
    "MetricStatistics",
    # Summary
    "StatisticalSummary",
    "ComparisonResult",
    "SignificanceLevel",
]
