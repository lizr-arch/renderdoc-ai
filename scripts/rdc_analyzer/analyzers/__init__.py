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

__all__ = [
    'OptimizationAdvisor',
    'OptimizationSuggestion',
    'OptimizationPriority',
    'OptimizationCategory',
    'ShaderAnalysisContext',
    'generate_optimization_report',
]