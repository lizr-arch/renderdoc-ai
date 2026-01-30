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
]