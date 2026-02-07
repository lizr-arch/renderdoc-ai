#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDC Analyzer - Analyzers Package
================================

分析模块：包含各种分析引擎。
"""

from .optimization_advisor import (
    OptimizationAdvisor,
    OptimizationSuggestion,
    OptimizationPriority,
    OptimizationCategory,
    ShaderAnalysisContext,
    generate_optimization_report,
)

# 核心分析器
from .frame import FrameAnalyzer
from .resource import ResourceAnalyzer
from .pass_analyzer import PassAnalyzer
from .state import StateAnalyzer
from .performance_analyzer import PerformanceAnalyzer

# Shader 性能多维度分析 (M4.3)
from .shader_perf_analyzer import (
    ShaderPerfAnalyzer,
    ShaderPerfResult,
    CycleMetrics,
    RegisterMetrics,
    DynamicMetrics,
    HealthLevel,
    get_gpu_options_for_dropdown,
    get_health_color,
    get_health_emoji,
    analyze_shader_batch,
    DEFAULT_GPU,
    # 评分算法函数（用于测试和自定义UI）
    calculate_cycles_score,
    calculate_register_score,
    calculate_weighted_cost,
    calculate_health_score,
)

__all__ = [
    # 优化建议模块
    'OptimizationAdvisor',
    'OptimizationSuggestion',
    'OptimizationPriority',
    'OptimizationCategory',
    'ShaderAnalysisContext',
    'generate_optimization_report',
    # 核心分析器
    'FrameAnalyzer',
    'ResourceAnalyzer',
    'PassAnalyzer',
    'StateAnalyzer',
    'PerformanceAnalyzer',
    # Shader 性能分析 (M4.3)
    'ShaderPerfAnalyzer',
    'ShaderPerfResult',
    'CycleMetrics',
    'RegisterMetrics',
    'DynamicMetrics',
    'HealthLevel',
    'get_gpu_options_for_dropdown',
    'get_health_color',
    'get_health_emoji',
    'analyze_shader_batch',
    'DEFAULT_GPU',
    # 评分算法函数
    'calculate_cycles_score',
    'calculate_register_score',
    'calculate_weighted_cost',
    'calculate_health_score',
]
